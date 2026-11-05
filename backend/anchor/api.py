"""L9 — FastAPI backend for the Anchor demo.

Every number the frontend shows comes from here. Classical solvers and Aer quantum
solvers run LIVE. IBM and D-Wave results are RECORDED runs (scripts/run_hardware.py),
returned with `replay: true` and their job / problem IDs.

Run:  uvicorn anchor.api:app --port 8030   (from backend/)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import mesh
from .candidates import Problem, make_problem
from .data import ROOT, Case, list_cases, load_case
from .graph import TAU_MM, TAU_REL
from .qubo import n_terms
from .registration import evaluate, reference_warp, region_grid, warp_from_selection
from .solvers import Instance, SolveResult, make_instance
from .solvers.registry import LIVE, META

RESULTS = ROOT / "results"
DIST = ROOT / "frontend" / "dist"
MAX_LIVE_QUANTUM_QUBITS = 20

app = FastAPI(title="Anchor", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- state
@dataclass
class Session:
    case: Case
    problem: Problem
    inst: Instance
    placement: mesh.Placement
    weight: np.ndarray            # per-vertex fade
    ref_disp: np.ndarray          # per-vertex displacement of the reference (true) shift
    grid: np.ndarray


_SESSIONS: dict[str, Session] = {}
_SOLVES: dict[tuple, dict] = {}
_CIRCUITS: dict[tuple, dict] = {}
_LOCK = threading.Lock()


class ProblemRequest(BaseModel):
    case_id: str = "Case5"
    n_used: int = Field(8, ge=3, le=16)
    k: int = Field(2, ge=1, le=3)
    outlier_rate: float = Field(0.3, ge=0.0, le=1.0)
    seed: int = 0


class SolveRequest(BaseModel):
    problem_id: str
    solver: str
    params: dict = Field(default_factory=dict)


def _pid(r: ProblemRequest) -> str:
    s = f"{r.case_id}|{r.n_used}|{r.k}|{r.outlier_rate:.3f}|{r.seed}"
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def _session(pid: str) -> Session:
    s = _SESSIONS.get(pid)
    if s is None:
        raise HTTPException(404, "unknown problem_id; create it with POST /api/problem")
    return s


def _r(a, nd=2):
    return np.round(np.asarray(a, float), nd).tolist()


# ---------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"ok": True, "cases": len(list_cases())}


@app.get("/api/solvers")
def solvers():
    hw = _hardware_index()
    out = []
    for key, meta in META.items():
        live = key in LIVE
        out.append({"id": key, **meta, "live": live,
                    "available": live or any(r["solver"] == key for r in hw)})
    return out


@app.get("/api/cases")
def cases():
    out = []
    for cid in list_cases():
        c = load_case(cid)
        out.append({"id": cid, "n_landmarks": c.n, "mean_shift_mm": round(float(c.shift_mm.mean()), 2),
                    "max_shift_mm": round(float(c.shift_mm.max()), 2)})
    return out


@app.get("/api/brain")
def brain():
    t = mesh.template()
    return {
        "n_vertices": len(t.pos), "n_faces": len(t.idx),
        "positions": mesh.b64(t.pos), "indices": mesh.b64(t.idx, np.uint32),
        "region": mesh.b64(t.region, np.uint8), "regions": t.meta["regions"],
        "ventricles": {"positions": mesh.b64(t.vpos), "indices": mesh.b64(t.vidx, np.uint32)},
        "frame": t.meta["frame"], "source": t.meta["source"],
    }


@app.post("/api/problem")
def problem(req: ProblemRequest):
    if req.case_id not in list_cases():
        raise HTTPException(404, f"unknown case {req.case_id}")
    pid = _pid(req)
    with _LOCK:
        if pid not in _SESSIONS:
            case = load_case(req.case_id)
            n_used = min(req.n_used, case.n - 3)          # keep >= 3 landmarks held out for scoring
            p = make_problem(case, n_used=n_used, k=req.k, outlier_rate=req.outlier_rate, seed=req.seed)
            inst = make_instance(p)
            pl = mesh.placement(case)
            t = mesh.template()
            w = mesh.fade(case, pl, t.pos)
            ref = mesh.surface_displacement(case, pl, reference_warp(case), w)
            _SESSIONS[pid] = Session(case, p, inst, pl, w, ref, region_grid(case))
    s = _SESSIONS[pid]
    p, inst, pl, case = s.problem, s.inst, s.placement, s.case
    iu = np.triu_indices(inst.m, 1)
    edges = [[int(a), int(b)] for a, b in zip(*iu) if inst.adj[a, b]]
    base = evaluate(case, p, np.zeros(inst.m, bool), s.grid)
    return {
        "problem_id": pid,
        "params": {"case_id": case.case_id, "n_used": p.n_used, "k": p.k,
                   "outlier_rate": p.outlier_rate, "seed": p.seed,
                   "tolerance": {"tau_mm": TAU_MM, "tau_rel": TAU_REL}},
        "case": {"id": case.case_id, "n_landmarks": case.n,
                 "mean_shift_mm": round(float(case.shift_mm.mean()), 2),
                 "max_shift_mm": round(float(case.shift_mm.max()), 2)},
        "placement": {"site": _r(pl.site), "normal": _r(pl.normal, 4), "offset": _r(pl.offset),
                      "note": "Template brain for display only; all errors are computed in patient space."},
        "landmarks": {
            "mri_used": _r(pl.to_scene(p.mri_used)),
            "us_used_true": _r(pl.to_scene(case.us[p.used_idx])),
            "mri_held": _r(pl.to_scene(case.mri[p.held_idx])),
            "us_held": _r(pl.to_scene(case.us[p.held_idx])),
        },
        "candidates": [
            {"id": i, "landmark": int(p.cand_landmark[i]), "pos": _r(pl.to_scene(p.cand_pos[i])),
             "score": round(float(p.cand_score[i]), 3), "kind": p.cand_kind[i], "true": bool(p.cand_true[i])}
            for i in range(inst.m)
        ],
        "graph": {"n_nodes": inst.m, "n_edges": len(edges), "edges": edges},
        "qubo": {"qubits": inst.m, **n_terms(inst.Q), "opt_weight": round(inst.opt_weight, 4),
                 "opt_size": int(inst.opt_x.sum())},
        "metrics": {"tre_uncorrected": round(base.tre_uncorrected, 3), "tre_oracle": round(base.tre_oracle, 3),
                    "n_held": int(len(p.held_idx))},
        "true_shift": {"displacement": mesh.b64(s.ref_disp), "weight": mesh.b64(s.weight),
                       "max_mm": round(float(np.linalg.norm(s.ref_disp, axis=1).max()), 2)},
    }


@app.post("/api/solve")
def solve(req: SolveRequest):
    s = _session(req.problem_id)
    key = (req.problem_id, req.solver, json.dumps(req.params, sort_keys=True))
    if key in _SOLVES:
        return _SOLVES[key]
    if req.solver in LIVE:
        if req.solver in ("qaoa", "danneal") and s.inst.m > MAX_LIVE_QUANTUM_QUBITS:
            raise HTTPException(400, f"live quantum simulation limited to {MAX_LIVE_QUANTUM_QUBITS} qubits")
        res: SolveResult = LIVE[req.solver](s.inst, **req.params)
    elif req.solver in ("ibm", "dwave"):
        res = _replay(s, req.solver, req.params)
    else:
        raise HTTPException(404, f"unknown solver {req.solver}")
    ev = evaluate(s.case, s.problem, res.selection, s.grid)
    disp = mesh.surface_displacement(s.case, s.placement, warp_from_selection(s.problem, res.selection), s.weight)
    err = np.linalg.norm(disp - s.ref_disp, axis=1)
    shown, clipped = mesh.clip_for_display(disp)
    out = {"result": res.as_dict(), "evaluation": ev.as_dict(), "meta": META.get(req.solver, {}),
           "displacement": mesh.b64(shown), "error": mesh.b64(err),
           "surface_error_max_mm": round(float(err.max()), 2),
           "surface_displacement_max_mm": round(float(np.linalg.norm(disp, axis=1).max()), 2),
           "display_clip_mm": mesh.DISPLAY_CLIP_MM, "display_clipped_fraction": round(clipped, 4)}
    _SOLVES[key] = out
    return out


@app.get("/api/circuit/{problem_id}")
def circuit(problem_id: str, p: int = 1):
    """Logical QAOA circuit (one layer by default) as SVG, plus Heron-transpiled stats."""
    s = _session(problem_id)
    if (problem_id, p) in _CIRCUITS:
        return _CIRCUITS[(problem_id, p)]
    from .solvers.quantum import build_circuit, device_stats
    import io
    import matplotlib
    matplotlib.use("Agg")
    from qiskit import transpile
    qc = build_circuit(s.inst.Q, p)
    qc.remove_final_measurements()
    # explicit gates (H, ZZ couplings, RZ, RX mixer) instead of opaque evolution boxes
    qc = transpile(qc, basis_gates=["h", "rz", "rx", "rzz"], optimization_level=0)
    buf = io.StringIO()
    fig = qc.draw("mpl", fold=-1, idle_wires=False, scale=0.7,
                  style={"name": "iqp-dark", "backgroundcolor": "#0b0f14"})
    fig.savefig(buf, format="svg", bbox_inches="tight", facecolor="#0b0f14")
    import matplotlib.pyplot as plt
    plt.close(fig)
    out = {"svg": buf.getvalue(), "stats": device_stats(s.inst.Q, p)}
    _CIRCUITS[(problem_id, p)] = out
    return out


@app.get("/api/benchmark")
def benchmark():
    f = RESULTS / "benchmark" / "summary.json"
    if not f.exists():
        raise HTTPException(404, "benchmark not run yet (scripts/run_benchmark.py)")
    return json.loads(f.read_text())


@app.get("/api/noise")
def noise():
    f = RESULTS / "noise" / "summary.json"
    if not f.exists():
        raise HTTPException(404, "noise study not run yet (scripts/run_noise.py)")
    return json.loads(f.read_text())


@app.get("/api/figure/{name}")
def figure(name: str):
    import re
    if not re.fullmatch(r"[\w.-]+\.(png|svg)", name):
        raise HTTPException(400, "bad figure name")
    f = RESULTS / "figures" / name
    if not f.exists():
        raise HTTPException(404, f"no figure {name}")
    return FileResponse(f)


@app.get("/api/hardware")
def hardware():
    return _hardware_index()


# ---------------------------------------------------------------- replay of recorded QPU runs
def _hardware_index() -> list[dict]:
    d = RESULTS / "hardware"
    out = []
    if d.exists():
        for f in sorted(d.glob("*.json")):
            try:
                rec = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            for run in rec.get("runs", []):
                out.append({"file": f.name, "solver": run["solver"], "params": run["problem"],
                            "label": run.get("label", ""), "backend": run.get("backend"),
                            "job_id": run.get("job_id") or run.get("problem_id"),
                            "timestamp": rec.get("timestamp")})
    return out


def _replay(s: Session, solver: str, params: dict) -> SolveResult:
    """Find a recorded run for exactly this problem and re-score its raw samples here."""
    from .solvers import summarise_samples
    want = {"case_id": s.problem.case_id, "n_used": s.problem.n_used, "k": s.problem.k,
            "outlier_rate": round(s.problem.outlier_rate, 3), "seed": s.problem.seed}
    label = params.get("label")
    d = RESULTS / "hardware"
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        rec = json.loads(f.read_text())
        for run in rec.get("runs", []):
            prob = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in run["problem"].items()}
            if run["solver"] != solver or prob != want or (label and run.get("label") != label):
                continue
            X = np.array(run["samples"]["bits"], dtype=bool)
            c = np.array(run["samples"]["counts"], dtype=float)
            res = summarise_samples(s.inst, X, c, solver, run.get("wall_time", 0.0),
                                    qpu_time=run.get("qpu_time"), circuit=run.get("circuit"),
                                    provenance={**run.get("provenance", {}), "file": f.name,
                                                "label": run.get("label"), "backend": run.get("backend"),
                                                "job_id": run.get("job_id"), "recorded_at": rec.get("timestamp")})
            res.replay = True
            return res
    raise HTTPException(404, f"no recorded {solver} run for this exact problem; "
                             f"hardware runs exist for: {[r['params'] for r in _hardware_index() if r['solver'] == solver]}")


# ---------------------------------------------------------------- built frontend (optional)
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
