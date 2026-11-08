"""Score recorded IBM hardware runs from their RAW bitstrings and compare them, on identical
circuits, with the ideal simulator and the Heron noise model (results/noise/summary.json).

    python scripts/analyze_hardware.py                      # newest results/hardware/ibm_*.json
    python scripts/analyze_hardware.py --file <path.json>   # any recorded or rehearsal file

-> results/hardware/analysis.json and results/figures/hardware.png (skipped for rehearsals,
   which write to results/hardware_rehearsal/ instead so they can never pass as hardware).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np  # noqa: E402

MODES = [("qaoa_p1", "QAOA, p = 1"), ("anneal_shallow", "Digitized anneal, p = 2"),
         ("anneal_deep", "Digitized anneal, deep (p = 5)")]


def score(rec_run):
    from anchor import hwset
    from anchor.registration import evaluate
    from anchor.qubo import energies
    from anchor.solvers import summarise_samples
    from anchor.solvers.classical import solve_exact
    pp = rec_run["problem"]
    case, prob, inst = hwset.build(pp["case_id"], pp["n_used"], pp["seed"])
    X = np.array(rec_run["samples"]["bits"], bool)
    c = np.array(rec_run["samples"]["counts"], float)
    r = summarise_samples(inst, X, c, "ibm", 0.0)
    ev = evaluate(case, prob, r.selection)
    ex = solve_exact(inst)
    # chance that a uniformly random bitstring is an optimal answer (m <= 12, so enumerate)
    allx = ((np.arange(2 ** inst.m)[:, None] >> np.arange(inst.m)) & 1).astype(bool)
    n_opt = int(np.isclose(energies(inst.Q, allx), inst.opt_energy, atol=1e-9).sum())
    return {"case_id": pp["case_id"], "qubits": inst.m, "mode": rec_run["provenance"]["mode"],
            "mitigated": rec_run["provenance"]["mitigation"] != "none",
            "p_feasible": r.p_feasible, "p_optimal": r.p_optimal, "approx_ratio": r.approx_ratio,
            "tre": ev.tre, "tre_uncorrected": ev.tre_uncorrected, "tre_oracle": ev.tre_oracle,
            "precision": ev.precision, "same_as_exact": bool((r.selection == ex.selection).all()),
            "best_shot_needed_repair": bool(r.repaired), "random_p_optimal": n_opt / 2 ** inst.m,
            "tre_exact": evaluate(case, prob, ex.selection).tre, "two_qubit_gates": rec_run["circuit"]["two_qubit_gates"],
            "shots": int(c.sum()), "job_id": rec_run["job_id"], "backend": rec_run["backend"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()
    if a.file:
        f = pathlib.Path(a.file)
    else:
        files = sorted((ROOT / "results" / "hardware").glob("ibm_*.json"))
        if not files:
            sys.exit("no IBM hardware file in results/hardware")
        f = files[-1]
    rec = json.loads(f.read_text())
    rows = [score(r) for r in rec["runs"]]

    noise = json.loads((ROOT / "results" / "noise" / "summary.json").read_text())
    ref = {(i["case_id"], i["qubits"]): i for i in noise["instances"]}
    for r in rows:
        i = ref.get((r["case_id"], r["qubits"]))
        if i:
            m = i["methods"][r["mode"]]
            r["ideal_p_feasible"] = m["ideal"]["p_feasible"]
            r["model_p_feasible"] = m["noisy"]["p_feasible"]
            r["random_p_feasible"] = i["random"]["p_feasible"]
            r["ideal_tre"] = m["ideal"]["tre"]

    print(f"{f.name}  backend {rows[0]['backend']}  rehearsal={rec.get('rehearsal', False)}")
    print(f"{'case':<7}{'q':>3} {'mode':<15}{'mit':>4} {'consistent':>10} {'model':>7} {'ideal':>7} {'random':>7} "
          f"{'optimal':>8} {'map err':>8} {'2q':>6}")
    for r in sorted(rows, key=lambda r: (r["case_id"], r["qubits"], r["mode"], r["mitigated"])):
        print(f"{r['case_id']:<7}{r['qubits']:>3} {r['mode']:<15}{'yes' if r['mitigated'] else 'no':>4} "
              f"{r['p_feasible']:>10.3f} {r.get('model_p_feasible', float('nan')):>7.3f} "
              f"{r.get('ideal_p_feasible', float('nan')):>7.3f} {r.get('random_p_feasible', float('nan')):>7.3f} "
              f"{r['p_optimal']:>8.3f} {r['tre']:>7.2f}mm {r['two_qubit_gates']:>6}")

    def mean(key, **w):
        v = [r[key] for r in rows if all(r[k] == x for k, x in w.items()) and r.get(key) is not None]
        return float(np.mean(v)) if v else None

    summary = {"file": f.name, "backend": rows[0]["backend"], "rehearsal": bool(rec.get("rehearsal")),
               "backend_snapshot": rec.get("backend_snapshot"), "n_runs": len(rows),
               "by_mode": {m: {"hardware_raw": mean("p_feasible", mode=m, mitigated=False),
                               "hardware_mitigated": mean("p_feasible", mode=m, mitigated=True),
                               "noise_model": mean("model_p_feasible", mode=m, mitigated=False),
                               "ideal": mean("ideal_p_feasible", mode=m, mitigated=False),
                               "random": mean("random_p_feasible", mode=m, mitigated=False),
                               "map_error_mitigated": mean("tre", mode=m, mitigated=True),
                               "map_error_raw": mean("tre", mode=m, mitigated=False)} for m, _ in MODES},
               "same_as_exact": f"{sum(r['same_as_exact'] for r in rows)}/{len(rows)}",
               "best_shot_needed_repair": f"{sum(r['best_shot_needed_repair'] for r in rows)}/{len(rows)}",
               "hardware_over_model": float(np.mean([r["p_feasible"] / r["model_p_feasible"] for r in rows
                                                     if not r["mitigated"] and r.get("model_p_feasible")])),
               "hardware_over_random": float(np.mean([r["p_feasible"] / r["random_p_feasible"] for r in rows
                                                      if r.get("random_p_feasible")])),
               "mitigated_over_raw": float(np.mean([a["p_feasible"] / b["p_feasible"] for a in rows if a["mitigated"]
                                                    for b in rows if not b["mitigated"] and b["case_id"] == a["case_id"]
                                                    and b["qubits"] == a["qubits"] and b["mode"] == a["mode"]])),
               "p_optimal_over_random": float(np.mean([r["p_optimal"] / r["random_p_optimal"] for r in rows])),
               "map_error_exact": mean("tre_exact"),
               "job_ids": sorted({(r["job_id"], "DD+twirling" if r["mitigated"] else "raw") for r in rows}),
               "map_error_uncorrected": mean("tre_uncorrected"), "map_error_best_possible": mean("tre_oracle"),
               "rows": rows}
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "backend_snapshot")}, indent=1))
    if summary["rehearsal"]:
        print("rehearsal: nothing written to results/")
        return
    (ROOT / "results" / "hardware" / "analysis.json").write_text(json.dumps(summary, indent=1))
    figure(rows, ROOT / "results" / "figures" / "hardware.png", rows[0]["backend"])
    print("wrote results/hardware/analysis.json and results/figures/hardware.png")


def figure(rows, path, backend):
    from run_benchmark import BG, COLOR, INK, MUTED, end_labels, style
    plt = style()
    sizes = sorted({r["qubits"] for r in rows})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True)
    series = [("ideal_p_feasible", False, "Ideal simulator", COLOR["exact"], "-"),
              ("model_p_feasible", False, "Heron noise model", COLOR["danneal"], "-"),
              ("p_feasible", False, f"{backend} raw", "#2fc27a", "-"),
              ("p_feasible", True, f"{backend} DD+twirling", "#2fc27a", (0, (3, 2)))]
    for ax, (mode, title) in zip(axes, MODES):
        labs = []
        for key, mit, lab, colr, ls in series:
            ys = []
            for n in sizes:
                v = [r[key] for r in rows if r["mode"] == mode and r["qubits"] == n and r["mitigated"] == mit
                     and r.get(key) is not None]
                ys.append(np.mean(v) if v else np.nan)
            ax.plot(sizes, ys, color=colr, ls=ls, marker="o", markeredgecolor=BG, markeredgewidth=2, label=lab)
            labs.append((sizes[-1], ys[-1], lab.replace("Heron noise model", "Noise model").replace("Ideal simulator", "Ideal"), colr))
        rnd = [np.mean([r["random_p_feasible"] for r in rows if r["qubits"] == n and r.get("random_p_feasible") is not None])
               for n in sizes]
        ax.plot(sizes, rnd, color=MUTED, ls=(0, (4, 3)), lw=1.4, label="Random guessing")
        labs.append((sizes[-1], rnd[-1], "Random", MUTED))
        ax.set_title(title)
        ax.set_xticks(sizes); ax.set_xlim(sizes[0] - 0.5, sizes[-1] + 4.2)
        ax.set_xlabel("Qubits"); ax.set_yscale("log")
        ax._labs = labs
    axes[0].set_ylabel("Shots that are a consistent set")
    fig.suptitle(f"Real hardware ({backend}) follows the noise model; deeper circuits lose the most", x=0.01, ha="left",
                 color=INK, fontsize=13, fontweight="bold")
    fig.tight_layout()
    for ax in axes:
        end_labels(ax, ax._labs)
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
