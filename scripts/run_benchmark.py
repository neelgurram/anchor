"""L8 — benchmark harness. Reproduces every number in results/benchmark and results/figures.

    python scripts/run_benchmark.py            # full sweep (~10 min on 16 cores)
    python scripts/run_benchmark.py --quick    # smoke test

Sweeps (fixed in CHARTER.md before any quantum run):
  classical : 22 cases x n_used {4,6,8,10,12} x outlier {0,0.2,0.4} x 5 seeds, k = 2
  quantum   : 22 cases x n_used {4,6,8} (8/12/16 qubits) x outlier {0.2,0.4} x 2 seeds,
              Aer statevector, every solver run on the same instances (paired comparison)
  scaling   : Heron-transpiled circuit cost vs qubits; exact max-clique time vs graph size
Uncertainty: 95% bootstrap CI over instances (2000 resamples).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

OUT = ROOT / "results" / "benchmark"
FIG = ROOT / "results" / "figures"

CLASSICAL = ["naive", "ransac", "exact", "sa"]
QUANTUM = ["danneal", "qaoa"]
LABEL = {"naive": "Naive (trust top match)", "ransac": "RANSAC", "exact": "Exact max clique",
         "sa": "Simulated annealing", "danneal": "Digitized anneal (gate)", "qaoa": "QAOA (gate)",
         "dwave": "D-Wave annealer", "ibm": "IBM hardware"}
SHORT = {"naive": "Naive", "ransac": "RANSAC", "exact": "Exact", "sa": "Sim. anneal",
         "danneal": "Digitized anneal", "qaoa": "QAOA", "dwave": "D-Wave", "ibm": "IBM"}
# fixed entity -> colour (dataviz reference palette, dark steps; validated on #0c1016)
COLOR = {"exact": "#3987e5", "danneal": "#d95926", "sa": "#199e70", "ransac": "#c98500",
         "dwave": "#d55181", "ibm": "#008300", "qaoa": "#9085e9", "naive": "#8794a3"}
BG, PANEL, INK, MUTED, GRID = "#06080b", "#0c1016", "#e6ecf2", "#8794a3", "#1c2430"


# ---------------------------------------------------------------- worker
def run_instance(task: dict) -> list[dict]:
    from anchor.candidates import make_problem
    from anchor.data import load_case
    from anchor.registration import evaluate, region_grid
    from anchor.solvers import make_instance
    from anchor.solvers.registry import LIVE

    case = load_case(task["case_id"])
    n_used = min(task["n_used"], case.n - 3)
    prob = make_problem(case, n_used=n_used, k=task["k"], outlier_rate=task["outlier_rate"], seed=task["seed"])
    inst = make_instance(prob)
    grid = region_grid(case)
    rows = []
    for s in task["solvers"]:
        kw = {"with_device_stats": False} if s in QUANTUM else {}
        res = LIVE[s](inst, seed=task["seed"], **kw)
        ev = evaluate(case, prob, res.selection, grid)
        rows.append({
            "sweep": task["sweep"], "case_id": case.case_id, "n_used": n_used, "k": task["k"],
            "qubits": inst.m, "outlier_rate": task["outlier_rate"], "seed": task["seed"], "solver": s,
            "tre": ev.tre, "tre_uncorrected": ev.tre_uncorrected, "tre_oracle": ev.tre_oracle,
            "tre_max": ev.tre_max, "map_error_max": ev.map_error_max,
            "precision": ev.precision, "recall": ev.recall, "n_selected": ev.n_selected,
            "approx_ratio": res.approx_ratio, "p_optimal": res.p_optimal, "p_feasible": res.p_feasible,
            "expected_ratio": res.expected_ratio, "wall_time": res.wall_time,
            "is_clique": res.approx_ratio is not None,
        })
    return rows


def device_cost(task: dict) -> dict:
    from anchor.candidates import make_problem
    from anchor.data import load_case
    from anchor.solvers import make_instance
    from anchor.solvers.quantum import device_stats
    case = load_case(task["case_id"])
    prob = make_problem(case, n_used=task["n_used"], k=task["k"], outlier_rate=0.3, seed=0)
    inst = make_instance(prob)
    st = device_stats(inst.Q, task["p"])
    return {"qubits": inst.m, "p": task["p"], **st}


# ---------------------------------------------------------------- stats
def boot_ci(x: np.ndarray, n: int = 2000, seed: int = 0) -> float:
    """Half-width of the 95% bootstrap CI of the mean."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float("nan")
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float((hi - lo) / 2)


def col(rows, key, **where):
    out = []
    for r in rows:
        if all(r[k] == v for k, v in where.items()):
            v = r[key]
            out.append(np.nan if v is None or v == "" else float(v))
    return np.array(out)


# ---------------------------------------------------------------- figures
def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.grid": True, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
        "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11, "axes.titlesize": 13,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
        "lines.linewidth": 2, "lines.markersize": 7,
    })
    return plt


def end_labels(ax, items, gap_pt=11, dx_pt=6):
    """Direct labels at line ends, pushed apart vertically so they never overlap.
    items: [(x, y, text, color)]"""
    fig = ax.figure
    fig.canvas.draw()
    to_pt = 72 / fig.dpi
    pts = [(ax.transData.transform((x, y))[1] * to_pt, x, y, t, c) for x, y, t, c in items]
    pts.sort(key=lambda r: r[0])
    placed = []
    for yp, *rest in pts:
        if placed and yp - placed[-1][0] < gap_pt:
            yp = placed[-1][0] + gap_pt
        placed.append((yp, *rest))
    # re-centre the stack around the mean of the true positions
    shift = np.mean([r[0] for r in pts]) - np.mean([r[0] for r in placed])
    for (yp, x, y, t, c), (y0, *_r) in zip(placed, pts):
        ax.annotate(t, (x, y), xytext=(dx_pt, yp + shift - y0), textcoords="offset points",
                    va="center", color=c, fontsize=9, annotation_clip=False)


def fig_tre_by_solver(plt, q_rows, path):
    order = ["naive", "ransac", "exact", "sa", "danneal", "qaoa"]
    unc = col(q_rows, "tre_uncorrected", solver="exact").mean()
    orc = col(q_rows, "tre_oracle", solver="exact").mean()
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    y = np.arange(len(order))[::-1]
    for yi, s in zip(y, order):
        v = col(q_rows, "tre", solver=s)
        m, ci = v.mean(), boot_ci(v)
        ax.barh(yi, m, height=0.56, color=COLOR[s], edgecolor=BG, linewidth=2)
        ax.errorbar(m, yi, xerr=ci, color=INK, capsize=3, lw=1.2)
        ax.text(m + ci + 0.08, yi, f"{m:.2f} mm", va="center", color=INK, fontsize=10)
    for x, name in [(unc, "no correction"), (orc, "best possible (true matches)")]:
        ax.axvline(x, color=MUTED, lw=1, ls=(0, (4, 3)))
        ax.text(x, len(order) - 0.35, f" {name}\n {x:.2f} mm", color=MUTED, fontsize=9, va="bottom")
    ax.set_yticks(y, [LABEL[s] for s in order])
    ax.set_xlabel("Map error at held-out expert landmarks (TRE, mm) — lower is better")
    ax.set_title("Which matches to trust decides the map error", pad=28)
    ax.set_xlim(0, max(unc, col(q_rows, "tre", solver="naive").mean()) * 1.25)
    ax.grid(axis="y", visible=False)
    n_inst = len(col(q_rows, "tre", solver="exact"))
    fig.text(0.01, 0.01, f"{n_inst} instances, 8–16 qubits, 20–40% bad matches, 22 RESECT patients. "
             "Whiskers: 95% bootstrap CI.", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_tre_vs_outlier(plt, c_rows, path):
    rates = sorted({r["outlier_rate"] for r in c_rows})
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    labels = []
    for key, name, colr, ls in [("tre_uncorrected", "No correction", MUTED, (0, (1, 2))),
                                ("tre_oracle", "Best possible", MUTED, (0, (4, 3)))]:
        ys = [col(c_rows, key, solver="exact", outlier_rate=r).mean() for r in rates]
        ax.plot(rates, ys, color=colr, ls=ls, lw=1.4, label=name)
        labels.append((rates[-1], ys[-1], name, MUTED))
    for s in CLASSICAL:
        ys = [col(c_rows, "tre", solver=s, outlier_rate=r).mean() for r in rates]
        ax.plot(rates, ys, color=COLOR[s], marker="o", label=SHORT[s],
                markeredgecolor=BG, markeredgewidth=2)
        labels.append((rates[-1], ys[-1], SHORT[s], INK))
    ax.set_xticks(rates, [f"{int(r*100)}%" for r in rates])
    ax.set_xlim(rates[0] - 0.02, rates[-1] + 0.12)
    ax.set_ylim(0, None)
    end_labels(ax, labels)
    ax.set_xlabel("Share of landmarks whose top ultrasound match is wrong")
    ax.set_ylabel("Map error (TRE, mm)")
    ax.set_title("Trusting the top match breaks as bad matches rise")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=9, ncol=6, handlelength=1.6)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_quality_vs_qubits(plt, q_rows, path):
    sizes = sorted({r["qubits"] for r in q_rows})
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    labs = ([], [])
    for s in ["sa", "danneal", "qaoa"]:
        a = [np.nanmean(col(q_rows, "approx_ratio", solver=s, qubits=n)) for n in sizes]
        b = [np.nanmean(col(q_rows, "p_optimal", solver=s, qubits=n)) for n in sizes]
        for ax, ys, lb in zip(axes, (a, b), labs):
            ax.plot(sizes, ys, color=COLOR[s], marker="o", label=SHORT[s], markeredgecolor=BG, markeredgewidth=2)
            lb.append((sizes[-1], ys[-1], SHORT[s], INK))
    axes[0].set_title("Answer quality after repair")
    axes[0].set_ylabel("Weight of chosen set / optimum")
    axes[0].set_ylim(0, 1.05)
    axes[1].set_title("Shots that land on the exact optimum")
    axes[1].set_ylabel("Fraction of shots")
    axes[1].set_ylim(0, 1.05)
    for ax in axes:
        ax.set_xticks(sizes)
        ax.set_xlim(sizes[0] - 1, sizes[-1] + 3.5)
        ax.set_xlabel("Qubits (candidate matches)")
    axes[0].legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    for ax, lb in zip(axes, labs):
        end_labels(ax, lb)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_device_cost(plt, dev, eps, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for p, colr in [(1, COLOR["exact"]), (3, COLOR["qaoa"])]:
        d = sorted([r for r in dev if r["p"] == p], key=lambda r: r["qubits"])
        q = [r["qubits"] for r in d]
        g = [r["two_qubit_gates"] for r in d]
        f = [math.exp(-n * eps) for n in g]
        axes[0].plot(q, g, color=colr, marker="o", markeredgecolor=BG, markeredgewidth=2, label=f"p = {p}")
        axes[1].plot(q, f, color=colr, marker="o", markeredgecolor=BG, markeredgewidth=2, label=f"p = {p}")

    axes[0].set_title("Two-qubit gates after compiling for IBM Heron")
    axes[0].set_ylabel("Two-qubit gates")
    axes[1].set_title("Chance a run sees no two-qubit error")
    axes[1].set_ylabel(f"exp(−gates × {eps:.1e})")
    axes[1].set_yscale("log")
    for ax in axes:
        ax.set_xlabel("Qubits")
        ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_classical_time(plt, timing, path):
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    n = [t["nodes"] for t in timing]
    ms = [t["median_ms"] for t in timing]
    ax.plot(n, ms, color=COLOR["exact"], marker="o", markeredgecolor=BG, markeredgewidth=2)
    ax.axhline(1000, color=MUTED, ls=(0, (4, 3)), lw=1)
    ax.text(n[0], 1100, "1 s: an intra-operative update budget", color=MUTED, fontsize=9)
    ax.set_yscale("log")
    ax.set_xlabel("Candidate matches (graph nodes) — landmarks × 4 candidates")
    ax.set_ylabel("Exact max-clique time (ms, median)")
    ax.set_title("Exact classical solve time vs problem size")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- scaling helpers
def heron_two_qubit_error() -> float:
    from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
    b = FakeMarrakesh()
    errs = [inst.error for name, d in b.target.items() if name in ("cz", "ecr", "cx")
            for inst in d.values() if inst is not None and inst.error is not None]
    return float(np.median(errs))


def clique_timing(sizes=(16, 32, 48, 64, 96, 128, 160), reps=5) -> list[dict]:
    """Synthetic consistency graphs with the density measured on RESECT: k = 4 candidates per
    landmark, true matches mutually consistent, decoy edges with probability q."""
    from anchor.qubo import max_weight_clique
    rng = np.random.default_rng(0)
    q = 0.22
    out = []
    for m in sizes:
        L = m // 4
        times = []
        for _ in range(reps):
            lm = np.repeat(np.arange(L), 4)
            true = np.zeros(m, bool)
            true[np.arange(L) * 4] = True
            adj = rng.random((m, m)) < q
            adj = np.triu(adj, 1)
            adj = adj | adj.T
            adj[np.ix_(true, true)] = True
            adj[lm[:, None] == lm[None, :]] = False
            w = 1 + 0.05 * rng.random(m)
            t0 = time.perf_counter()
            max_weight_clique(adj, w)
            times.append((time.perf_counter() - t0) * 1000)
        out.append({"nodes": m, "landmarks": L, "median_ms": float(np.median(times)), "max_ms": float(max(times))})
        print(f"  clique timing {m:4d} nodes: {np.median(times):9.2f} ms")
    return out


def measured_decoy_density(rows_inst) -> float:
    return float(np.mean(rows_inst)) if rows_inst else float("nan")


def smoothing_check(cases, seeds=(0, 1, 2)) -> dict:
    """Charter change log: TRE with TPS smoothing 0 vs 100, classical solvers, n_used 8, 30%."""
    import anchor.registration as reg
    from anchor.candidates import make_problem
    from anchor.data import load_case
    from anchor.solvers import make_instance
    from anchor.solvers.registry import LIVE
    out = {}
    for sm in (0.0, reg.SMOOTHING):
        old, reg.SMOOTHING = reg.SMOOTHING, sm
        acc = {s: [] for s in ["naive", "exact", "oracle"]}
        for cid in cases:
            case = load_case(cid)
            grid = reg.region_grid(case)
            for seed in seeds:
                prob = make_problem(case, n_used=8, k=2, outlier_rate=0.3, seed=seed)
                inst = make_instance(prob)
                for s in ["naive", "exact"]:
                    ev = reg.evaluate(case, prob, LIVE[s](inst).selection, grid)
                    acc[s].append(ev.tre)
                acc["oracle"].append(ev.tre_oracle)
        reg.SMOOTHING = old
        out[str(sm)] = {k: round(float(np.mean(v)), 3) for k, v in acc.items()}
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--skip-sweeps", action="store_true", help="re-make figures from runs.csv")
    a = ap.parse_args()

    from anchor.data import list_cases
    cases = list_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    if a.quick:
        cases = cases[:3]
        c_grid = dict(n_used=[6, 8], outlier=[0.0, 0.4], seeds=[0])
        q_grid = dict(n_used=[4, 6], outlier=[0.4], seeds=[0])
    else:
        c_grid = dict(n_used=[4, 6, 8, 10, 12], outlier=[0.0, 0.2, 0.4], seeds=[0, 1, 2, 3, 4])
        q_grid = dict(n_used=[4, 6, 8], outlier=[0.2, 0.4], seeds=[0, 1])

    tasks = []
    for cid in cases:
        for n in c_grid["n_used"]:
            for r in c_grid["outlier"]:
                for sd in c_grid["seeds"]:
                    tasks.append(dict(sweep="classical", case_id=cid, n_used=n, k=2, outlier_rate=r, seed=sd, solvers=CLASSICAL))
        for n in q_grid["n_used"]:
            for r in q_grid["outlier"]:
                for sd in q_grid["seeds"]:
                    # seeds offset by 100 so the quantum set is not a subset of the classical one
                    tasks.append(dict(sweep="quantum", case_id=cid, n_used=n, k=2, outlier_rate=r, seed=100 + sd,
                                      solvers=CLASSICAL + QUANTUM))

    runs_csv = OUT / "runs.csv"
    t0 = time.time()
    if a.skip_sweeps and runs_csv.exists():
        with open(runs_csv) as fh:
            rows = []
            for r in csv.DictReader(fh):
                for k in ("n_used", "k", "qubits", "seed", "n_selected"):
                    r[k] = int(r[k])
                for k in ("outlier_rate",):
                    r[k] = float(r[k])
                rows.append(r)
    else:
        # quantum tasks first: they are the long ones
        tasks.sort(key=lambda t: (t["sweep"] != "quantum", -t["n_used"]))
        rows = []
        print(f"{len(tasks)} instances on {a.workers} workers")
        with ProcessPoolExecutor(a.workers) as ex:
            for i, rs in enumerate(ex.map(run_instance, tasks, chunksize=1)):
                rows.extend(rs)
                if (i + 1) % 100 == 0:
                    print(f"  {i+1}/{len(tasks)}  {time.time()-t0:.0f}s")
        with open(runs_csv, "w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
        print(f"sweeps done in {time.time()-t0:.0f}s -> {runs_csv}")

    c_rows = [r for r in rows if r["sweep"] == "classical"]
    q_rows = [r for r in rows if r["sweep"] == "quantum"]

    # circuit cost vs size (transpile only; no simulation)
    dev_tasks = [dict(case_id="Case12", n_used=n, k=2, p=p) for p in (1, 3) for n in (4, 6, 8, 10, 12)]
    dev_tasks += [dict(case_id="Case12", n_used=10, k=3, p=p) for p in (1, 3)]   # 30 qubits
    if a.quick:
        dev_tasks = [t for t in dev_tasks if t["n_used"] <= 6]
    with ProcessPoolExecutor(a.workers) as ex:
        dev = list(ex.map(device_cost, dev_tasks))
    eps = heron_two_qubit_error()
    timing = clique_timing(sizes=(16, 32, 48) if a.quick else (16, 32, 48, 64, 96, 128, 160))
    smooth = smoothing_check(cases[:3] if a.quick else cases)

    # headline: paired comparison on the quantum set
    headline = []
    for s in ["naive", "ransac", "exact", "sa", "danneal", "qaoa"]:
        tre = col(q_rows, "tre", solver=s)
        ar = col(q_rows, "approx_ratio", solver=s)
        headline.append({
            "solver": s, "label": LABEL[s], "tre": round(float(tre.mean()), 3), "tre_ci": round(boot_ci(tre), 3),
            "precision": round(float(np.nanmean(col(q_rows, "precision", solver=s))), 3),
            # naive / RANSAC do not optimise the QUBO, so a ratio to its optimum is not meaningful
            "approx_ratio": None if s in ("naive", "ransac") else round(float(np.nanmean(ar)), 3),
            "consistent_set_rate": round(float(np.mean(~np.isnan(ar))), 3),
            "p_optimal": None if s in ("naive", "ransac", "exact") else
                round(float(np.nanmean(col(q_rows, "p_optimal", solver=s))), 4),
            "wall_time_s": round(float(np.mean(col(q_rows, "wall_time", solver=s))), 3),
            "n": int(len(tre)),
        })
    # paired differences on identical instances (row order per instance is fixed)
    def paired(a, b):
        d = col(q_rows, "tre", solver=a) - col(q_rows, "tre", solver=b)
        return {"mean_mm": round(float(d.mean()), 3), "ci95_mm": round(boot_ci(d), 3),
                "a_better_share": round(float((d < -1e-9).mean()), 3), "b_better_share": round(float((d > 1e-9).mean()), 3)}
    paired_diff = {f"{a}-{b}": paired(a, b) for a, b in
                   [("exact", "ransac"), ("exact", "naive"), ("qaoa", "exact"), ("danneal", "exact"), ("sa", "exact")]}
    by_outlier = {}
    for r in sorted({x["outlier_rate"] for x in c_rows}):
        by_outlier[str(r)] = {s: round(float(col(c_rows, "tre", solver=s, outlier_rate=r).mean()), 3) for s in CLASSICAL}
        by_outlier[str(r)]["uncorrected"] = round(float(col(c_rows, "tre_uncorrected", solver="exact", outlier_rate=r).mean()), 3)
        by_outlier[str(r)]["oracle"] = round(float(col(c_rows, "tre_oracle", solver="exact", outlier_rate=r).mean()), 3)
    by_qubits = {}
    for n in sorted({x["qubits"] for x in q_rows}):
        by_qubits[str(n)] = {s: {"approx_ratio": round(float(np.nanmean(col(q_rows, "approx_ratio", solver=s, qubits=n))), 3),
                                 "p_optimal": round(float(np.nanmean(col(q_rows, "p_optimal", solver=s, qubits=n))), 4),
                                 "p_feasible": round(float(np.nanmean(col(q_rows, "p_feasible", solver=s, qubits=n))), 4),
                                 "tre": round(float(col(q_rows, "tre", solver=s, qubits=n).mean()), 3)}
                             for s in ["sa", "danneal", "qaoa"]}
    # revisit trigger: 2q error rate at which a p = 3 circuit at this size has >= 50% error-free runs
    trigger = [{"qubits": r["qubits"], "p": r["p"], "two_qubit_gates": r["two_qubit_gates"],
                "error_free_now": round(math.exp(-r["two_qubit_gates"] * eps), 4),
                "eps_needed_for_50pct": float(f"{math.log(2) / r['two_qubit_gates']:.2e}")}
               for r in sorted(dev, key=lambda r: (r["p"], r["qubits"]))]

    plt = style()
    figs = {
        "tre_by_solver.png": lambda pth: fig_tre_by_solver(plt, q_rows, pth),
        "tre_vs_outlier.png": lambda pth: fig_tre_vs_outlier(plt, c_rows, pth),
        "quality_vs_qubits.png": lambda pth: fig_quality_vs_qubits(plt, q_rows, pth),
        "device_cost.png": lambda pth: fig_device_cost(plt, dev, eps, pth),
        "classical_time.png": lambda pth: fig_classical_time(plt, timing, pth),
    }
    for name, fn in figs.items():
        fn(FIG / name)

    summary = {
        "generated": time.strftime("%Y-%m-%d %H:%M"), "quick": a.quick,
        "sweeps": {"classical": {**c_grid, "cases": len(cases), "instances": len(c_rows) // len(CLASSICAL)},
                   "quantum": {**q_grid, "cases": len(cases), "instances": len(q_rows) // (len(CLASSICAL) + len(QUANTUM)),
                               "backend": "qiskit-aer statevector", "seed_offset": 100}},
        "headline": headline, "paired_tre_difference": paired_diff, "by_outlier": by_outlier, "by_qubits": by_qubits,
        "device_cost": sorted(dev, key=lambda r: (r["p"], r["qubits"])), "heron_median_2q_error": eps,
        "revisit_trigger": trigger, "classical_clique_timing": timing,
        "smoothing_check": smooth, "figures": list(figs),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(headline, indent=1))
    print(f"total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
