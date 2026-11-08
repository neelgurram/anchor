"""L7 — real quantum hardware runs. Run ONLY with Neel's explicit go.

    python scripts/run_hardware.py --dry-run            # build everything, print the plan, no network
    python scripts/run_hardware.py --ibm                # one raw + one mitigated job on the least-busy Heron
    python scripts/run_hardware.py --dwave              # D-Wave Advantage via Leap
    python scripts/run_hardware.py --ibm --dwave

Credentials are typed in at run time (getpass) or read from the environment
(IBM_API_KEY / IBM_INSTANCE_CRN, DWAVE_API_TOKEN). They are never written anywhere.

Output: results/hardware/{ibm,dwave}_<timestamp>.json in the format the app replays:
  {"timestamp", "backend_snapshot", "runs": [{"solver", "problem", "label", "samples": {"bits", "counts"},
    "backend", "job_id", "qpu_time", "circuit", "provenance", "wall_time"}]}
Every run stores the RAW bitstrings; the app and the notebook re-score them from scratch.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from getpass import getpass

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np  # noqa: E402

from anchor import hwset  # noqa: E402
from anchor.solvers.quantum import bits_to_x, build_circuit  # noqa: E402

OUT = ROOT / "results" / "hardware"
REHEARSAL = ROOT / "results" / "hardware_rehearsal"


def secret(env: str, prompt: str) -> str:
    v = os.environ.get(env)
    return (v if v else getpass(prompt)).strip()   # pasted keys often carry a stray space or newline


def backend_snapshot(backend) -> dict:
    snap = {"name": backend.name, "num_qubits": backend.num_qubits}
    try:
        t = backend.target
        two = [i.error for n, d in t.items() if n in ("cz", "ecr", "cx") for i in d.values() if i and i.error is not None]
        ro = [i.error for i in t["measure"].values() if i and i.error is not None]
        snap.update({"median_2q_error": float(np.median(two)), "median_readout_error": float(np.median(ro))})
        props = backend.properties()
        if props is not None:
            snap["calibration_time"] = str(props.last_update_date)
            snap["median_t1_us"] = float(np.median([props.t1(q) for q in range(backend.num_qubits)]) * 1e6)
            snap["median_t2_us"] = float(np.median([props.t2(q) for q in range(backend.num_qubits)]) * 1e6)
    except Exception as e:  # snapshot is best-effort; never block a paid run on it
        snap["snapshot_error"] = repr(e)
    return snap


# ---------------------------------------------------------------- IBM
def run_ibm(shots: int, dry: bool, backend_name: str | None, rehearse: bool = False):
    from qiskit.transpiler import generate_preset_pass_manager
    items = []
    for cid, n, seed in hwset.gate_set():
        case, prob, inst = hwset.build(cid, n, seed)
        for key, mode in hwset.gate_modes(inst, seed).items():
            items.append({"problem": hwset.problem_params(cid, n, seed), "inst": inst, "mode": key, **mode})
    print(f"IBM plan: {len(items)} circuits x 2 (raw, mitigated) x {shots} shots "
          f"= {2 * len(items) * shots:,} shots, in 2 jobs")

    if dry or rehearse:
        from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
        backend = FakeMarrakesh()          # rehearse: Sampler runs locally on Aer with this noise model
    else:
        from qiskit_ibm_runtime import QiskitRuntimeService
        service = QiskitRuntimeService(channel="ibm_quantum_platform",
                                       token=secret("IBM_API_KEY", "IBM API key: "),
                                       instance=secret("IBM_INSTANCE_CRN", "Instance CRN: "))
        backend = service.backend(backend_name) if backend_name else \
            service.least_busy(operational=True, simulator=False, min_num_qubits=24)
    print("Backend:", backend.name)
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=7)
    pubs = []
    for it in items:
        isa = pm.run(build_circuit(it["inst"].Q, it["layers"]))
        ops = isa.count_ops()
        it["circuit"] = {"qubits": it["inst"].m, "layers": it["layers"], "depth": int(isa.depth()),
                         "two_qubit_gates": int(sum(v for k, v in ops.items() if k in ("cz", "ecr", "cx"))),
                         "device": backend.name}
        pubs.append((isa, it["params"]))
        print(f"  {it['problem']['case_id']} {it['inst'].m:2d}q {it['label']:<24} "
              f"2q={it['circuit']['two_qubit_gates']:5d} depth={it['circuit']['depth']}")
    if dry:
        print("dry run: nothing sent.")
        return

    from qiskit_ibm_runtime import SamplerV2 as Sampler
    snap = backend_snapshot(backend)
    runs = []
    out_file = None
    for mitigated in (True, False):
        s = Sampler(mode=backend)
        s.options.default_shots = shots
        if mitigated:
            s.options.dynamical_decoupling.enable = True
            s.options.dynamical_decoupling.sequence_type = "XY4"
            s.options.twirling.enable_gates = True
            s.options.twirling.enable_measure = True
        t0 = time.time()
        job = s.run(pubs)
        print(f"submitted {'mitigated' if mitigated else 'raw'} job {job.job_id()} — waiting (queue may take a while)")
        res = job.result()
        wall = time.time() - t0
        try:
            qsec = float(job.metrics()["usage"]["quantum_seconds"])
        except Exception:
            qsec = None
        for it, r in zip(items, res):
            counts = r.data.meas.get_counts()
            keys = list(counts)
            runs.append({
                "solver": "ibm", "problem": it["problem"],
                "label": f"{it['label']} · {'DD+twirling' if mitigated else 'raw'}",
                "samples": {"bits": [[int(b) for b in bits_to_x(k)] for k in keys], "counts": [counts[k] for k in keys]},
                "backend": backend.name, "job_id": job.job_id(), "qpu_time": qsec, "wall_time": wall,
                "circuit": it["circuit"],
                "provenance": {"mode": it["mode"], "family": it["family"], "layers": it["layers"],
                               "params": [round(float(v), 5) for v in it["params"]],
                               "params_source": "ideal Aer simulator (transferred unchanged)",
                               "mitigation": "XY4 dynamical decoupling + gate/measure twirling" if mitigated else "none",
                               "shots": shots, "transpile": "preset level 3, seed 7",
                               "qpu_seconds_whole_job": qsec},
            })
        # save after EVERY job, so a failure in the second job never loses the first
        out_file = save("ibm", runs, snap, rehearse, out_file)


# ---------------------------------------------------------------- D-Wave
def run_dwave(reads: int, dry: bool, solver: str | None):
    from anchor.solvers.dwave import sample_dwave
    items = [(cid, n, seed) for cid, n, seed in hwset.anneal_set()]
    print(f"D-Wave plan: {len(items)} problems x {reads} reads (each ~0.1-0.2 s QPU access; trial = 60 s)")
    for cid, n, seed in items:
        print(f"  {cid} {2 * n:2d} variables")
    if dry:
        print("dry run: nothing sent.")
        return
    token = secret("DWAVE_API_TOKEN", "D-Wave Leap API token: ")
    runs, used = [], 0.0
    for cid, n, seed in items:
        case, prob, inst = hwset.build(cid, n, seed)
        X, c, info = sample_dwave(inst, token, num_reads=reads, solver=solver)
        used += info["qpu_time"] or 0
        print(f"  {cid} {inst.m:2d} vars: problem {info['problem_id']}, QPU {info['qpu_time']:.3f}s, "
              f"chain max {info['circuit']['max_chain_length']} — total QPU {used:.2f}s")
        runs.append({
            "solver": "dwave", "problem": hwset.problem_params(cid, n, seed),
            "label": f"Advantage · {reads} reads",
            "samples": {"bits": X.astype(int).tolist(), "counts": [int(v) for v in c]},
            "backend": info["device"], "job_id": info["problem_id"], "qpu_time": info["qpu_time"],
            "wall_time": info["wall_time"], "circuit": info["circuit"],
            "provenance": {"num_reads": reads, "timing_us": info["timing_us"],
                           "annealing_time_us": info["annealing_time_us"], "embedding": "minorminer (EmbeddingComposite)"},
        })
        if used > 35:      # keep ~25 s of the 60 s trial in reserve
            print("stopping: QPU budget reserve reached")
            break
    save("dwave", runs, {"device": runs[0]["backend"] if runs else None, "qpu_seconds_used": used})


def save(kind, runs, snap, rehearse: bool = False, f: pathlib.Path | None = None) -> pathlib.Path:
    # rehearsals go to a separate, git-ignored folder so the app never replays simulated data as hardware
    d = REHEARSAL if rehearse else OUT
    d.mkdir(parents=True, exist_ok=True)
    if f is None:
        f = d / f"{kind}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "backend_snapshot": snap,
                             "rehearsal": rehearse, "runs": runs}, indent=1))
    print("saved", f, f"({len(runs)} runs)")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ibm", action="store_true")
    ap.add_argument("--dwave", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rehearse", action="store_true",
                    help="IBM only: run the exact same code path locally on the FakeMarrakesh noise model "
                         "(no account, no QPU time); output goes to results/hardware_rehearsal/")
    ap.add_argument("--shots", type=int, default=4000)
    ap.add_argument("--reads", type=int, default=1000)
    ap.add_argument("--ibm-backend")
    ap.add_argument("--dwave-solver")
    a = ap.parse_args()
    if not (a.ibm or a.dwave):
        ap.error("choose --ibm and/or --dwave (add --dry-run to only print the plan)")
    if not (a.dry_run or a.rehearse):
        ok = input("This spends real QPU time. Has Neel approved this run? Type YES: ")
        if ok.strip() != "YES":
            sys.exit("aborted")
    if a.ibm:
        run_ibm(a.shots, a.dry_run, a.ibm_backend, a.rehearse)
    if a.dwave:
        run_dwave(a.reads, a.dry_run, a.dwave_solver)


if __name__ == "__main__":
    main()
