"""Noise analysis, simulated leg: ideal statevector vs IBM Heron noise model (FakeMarrakesh),
on the exact instances the IBM hardware run uses (anchor.hwset). Uniform random bitstrings
are the floor: a noisy device that does not beat them has lost the signal.

    python scripts/run_noise.py          -> results/noise/summary.json, results/figures/noise.png
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402

OUT = ROOT / "results" / "noise"
SHOTS = 2000


def score(case, prob, inst, X, c):
    from anchor.registration import evaluate
    from anchor.solvers import summarise_samples
    r = summarise_samples(inst, X, c, "x", 0.0)
    ev = evaluate(case, prob, r.selection)
    return {"p_feasible": r.p_feasible, "p_optimal": r.p_optimal, "expected_ratio": r.expected_ratio,
            "approx_ratio": r.approx_ratio, "tre": ev.tre, "tre_uncorrected": ev.tre_uncorrected,
            "tre_oracle": ev.tre_oracle, "precision": ev.precision}


def job(task):
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
    from anchor import hwset
    from anchor.solvers.quantum import build_circuit, counts_to_arrays, lr_params, run_local, solve_qaoa, tune_anneal

    cid, n, seed = task
    case, prob, inst = hwset.build(cid, n, seed)
    Q = inst.Q
    # angles fixed on the ideal simulator, then transferred unchanged (what the hardware run does)
    q1 = solve_qaoa(inst, p=1, shots=2048, maxiter=60, seed=seed, with_device_stats=False)
    qaoa_params = np.array(q1.provenance["params"])
    p_lr, d_lr = tune_anneal(Q, ps=(2, 3, 5), seed=seed)
    methods = {"qaoa_p1": (1, qaoa_params), f"lr_p{p_lr}": (p_lr, lr_params(p_lr, d_lr))}

    fake = FakeMarrakesh()
    noisy = AerSimulator.from_backend(fake)
    out = {"case_id": cid, "n_used": n, "seed": seed, "qubits": inst.m, "methods": {}}
    rng = np.random.default_rng(seed)
    Xr = rng.random((SHOTS, inst.m)) < 0.5
    out["random"] = score(case, prob, inst, Xr, np.ones(SHOTS))
    for name, (p, params) in methods.items():
        ideal = run_local(Q, p, params, shots=SHOTS, seed=seed + 7)
        qc = build_circuit(Q, p).assign_parameters(params)
        tqc = transpile(qc, fake, optimization_level=3, seed_transpiler=7)
        t0 = time.perf_counter()
        nc = noisy.run(tqc, shots=SHOTS, seed_simulator=seed + 7).result().get_counts()
        ops = tqc.count_ops()
        out["methods"][name] = {
            "layers": p, "params": [round(float(v), 5) for v in params],
            "two_qubit_gates": int(sum(v for k, v in ops.items() if k in ("cz", "ecr", "cx"))),
            "depth": int(tqc.depth()),
            "ideal": score(case, prob, inst, *counts_to_arrays(ideal)),
            "noisy": score(case, prob, inst, *counts_to_arrays(nc)),
            "noisy_sim_seconds": round(time.perf_counter() - t0, 2),
        }
    print(f"  {cid} n={n}: done", flush=True)
    return out


def figure(rows, path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_benchmark import BG, COLOR, INK, MUTED, end_labels, style
    plt = style()
    sizes = sorted({r["qubits"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3), sharey=True)
    labs = {0: [], 1: []}
    for ai, (ax, meth_prefix, title) in enumerate( [(axes[0], "qaoa_p1", "QAOA, p = 1 (angles from simulator)"),
                                   (axes[1], "lr_", "Digitized anneal (linear ramp)")]):
        series = [("ideal", "Ideal simulator", COLOR["exact"]), ("noisy", "Heron noise model", COLOR["danneal"])]
        for key, lab, colr in series:
            ys = []
            for n in sizes:
                v = [m[key]["p_feasible"] for r in rows if r["qubits"] == n
                     for k, m in r["methods"].items() if k.startswith(meth_prefix)]
                ys.append(np.mean(v))
            ax.plot(sizes, ys, color=colr, marker="o", markeredgecolor=BG, markeredgewidth=2, label=lab)
            labs[ai].append((sizes[-1], ys[-1], lab, INK))
        rnd = [np.mean([r["random"]["p_feasible"] for r in rows if r["qubits"] == n]) for n in sizes]
        ax.plot(sizes, rnd, color=MUTED, ls=(0, (4, 3)), lw=1.4, label="Random guessing")
        labs[ai].append((sizes[-1], rnd[-1], "Random", MUTED))
        ax.set_title(title)
        ax.set_xticks(sizes)
        ax.set_xlim(sizes[0] - 0.5, sizes[-1] + 3.2)
        ax.set_xlabel("Qubits")
        ax.set_yscale("log")
    axes[0].set_ylabel("Shots that are a consistent set")
    axes[0].legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    for ai, ax in enumerate(axes):
        end_labels(ax, labs[ai])
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    from anchor import hwset
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = hwset.gate_set()
    t0 = time.time()
    with ProcessPoolExecutor(min(len(tasks), max(1, (os.cpu_count() or 2) - 2))) as ex:
        rows = list(ex.map(job, tasks))
    from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M"), "shots": SHOTS,
               "noise_model": "AerSimulator.from_backend(FakeMarrakesh) — Heron r2 calibration snapshot",
               "instances": rows}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    figure(rows, ROOT / "results" / "figures" / "noise.png")
    for r in rows:
        line = " ".join(f"{k}: ideal {m['ideal']['p_feasible']:.3f} noisy {m['noisy']['p_feasible']:.3f} ({m['two_qubit_gates']} 2q)"
                        for k, m in r["methods"].items())
        print(f"{r['case_id']} {r['qubits']:2d}q random {r['random']['p_feasible']:.3f} | {line}")
    print(f"total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
