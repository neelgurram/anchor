"""Classical vs gate-based quantum vs quantum annealing, on the SAME fixed hardware instances.

For every (patient, size) in anchor.hwset it scores:
  classical   exact max clique (always optimal)  +  simulated annealing (classical annealer)
  gate        IBM Heron QAOA p = 1, DD + twirling          (recorded results/hardware/ibm_*.json)
  annealing   digitized anneal on IBM Heron, p = 2           (same IBM file)
              D-Wave Advantage, real quantum annealer        (results/hardware/dwave_*.json, if run)

Two numbers per method: the chance one shot/read is the best answer, and the map error (mm,
held-out landmarks) of the answer the method finally returns.

    python scripts/compare_paradigms.py
-> results/paradigms/summary.json and results/figures/paradigms.png
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np  # noqa: E402

METHODS = [  # key, label, family, colour key
    ("exact", "Exact search (classical)", "classical", "exact"),
    ("sa", "Simulated annealing (classical)", "classical", "sa"),
    ("ibm_qaoa", "QAOA on IBM (gate)", "gate", "qaoa"),
    ("ibm_anneal", "Digitized anneal on IBM (gate)", "gate", "danneal"),
    ("dwave", "D-Wave annealer (quantum anneal)", "anneal", "dwave"),
]


def newest(pattern):
    f = sorted((ROOT / "results" / "hardware").glob(pattern))
    return f[-1] if f else None


def recorded(path, pick):
    """{(case_id, qubits): run} for runs in a hardware file that `pick` accepts."""
    if path is None:
        return {}, None
    rec = json.loads(path.read_text())
    if rec.get("rehearsal"):
        sys.exit(f"{path.name} is a rehearsal, not hardware")
    out = {}
    for r in rec["runs"]:
        if pick(r):
            pp = r["problem"]
            out[(pp["case_id"], 2 * pp["n_used"])] = r
    return out, path.name


def main():
    from anchor import hwset
    from anchor.registration import evaluate
    from anchor.solvers import summarise_samples
    from anchor.solvers.classical import solve_exact, solve_sa

    ibm_file = newest("ibm_*.json")
    qaoa, ibm_name = recorded(ibm_file, lambda r: r["provenance"]["mode"] == "qaoa_p1"
                              and r["provenance"]["mitigation"] != "none")
    anneal, _ = recorded(ibm_file, lambda r: r["provenance"]["mode"] == "anneal_shallow"
                         and r["provenance"]["mitigation"] != "none")
    dwave, dwave_name = recorded(newest("dwave_*.json"), lambda r: True)

    rows = []
    for cid, n, seed in hwset.anneal_set():
        case, prob, inst = hwset.build(cid, n, seed)
        q = inst.m
        row = {"case_id": cid, "qubits": q, "uncorrected": None, "best_possible": None}

        t0 = time.perf_counter()
        ex = solve_exact(inst)
        ev = evaluate(case, prob, ex.selection)
        row["uncorrected"], row["best_possible"] = ev.tre_uncorrected, ev.tre_oracle
        row["exact"] = {"p_optimal": 1.0, "tre": ev.tre, "seconds": time.perf_counter() - t0}

        sa = solve_sa(inst, num_reads=1000, seed=seed)
        row["sa"] = {"p_optimal": sa.p_optimal, "tre": evaluate(case, prob, sa.selection).tre,
                     "seconds": sa.wall_time, "same_as_exact": bool((sa.selection == ex.selection).all())}

        for key, src in (("ibm_qaoa", qaoa), ("ibm_anneal", anneal), ("dwave", dwave)):
            r = src.get((cid, q))
            if r is None:
                row[key] = None
                continue
            X = np.array(r["samples"]["bits"], bool)
            c = np.array(r["samples"]["counts"], float)
            res = summarise_samples(inst, X, c, key, 0.0)
            row[key] = {"p_optimal": res.p_optimal, "p_feasible": res.p_feasible,
                        "tre": evaluate(case, prob, res.selection).tre,
                        "same_as_exact": bool((res.selection == ex.selection).all()),
                        "qpu_seconds": r.get("qpu_time"), "job_id": r["job_id"], "backend": r["backend"]}
        rows.append(row)

    def agg(key):
        got = [r[key] for r in rows if r[key] is not None]
        if not got:
            return None
        return {"instances": len(got), "mean_p_optimal": float(np.mean([g["p_optimal"] for g in got])),
                "mean_map_error": float(np.mean([g["tre"] for g in got])),
                "same_as_exact": f"{sum(g.get('same_as_exact', True) for g in got)}/{len(got)}",
                "sizes": sorted({r["qubits"] for r in rows if r[key] is not None})}

    summary = {"ibm_file": ibm_name, "dwave_file": dwave_name,
               "dwave_status": "recorded" if dwave_name else "not run yet",
               "methods": {k: {"label": lab, "family": fam, **(agg(k) or {"instances": 0})}
                           for k, lab, fam, _ in METHODS},
               "rows": rows}
    out = ROOT / "results" / "paradigms"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))

    print(f"IBM: {ibm_name}   D-Wave: {dwave_name or 'not run yet'}")
    print(f"{'method':<36}{'n':>3}{'P(best) per shot':>18}{'map err':>10}{'= exact':>9}")
    for k, lab, _, _ in METHODS:
        m = summary["methods"][k]
        if m["instances"]:
            print(f"{lab:<36}{m['instances']:>3}{m['mean_p_optimal']:>18.3f}{m['mean_map_error']:>8.2f}mm"
                  f"{m['same_as_exact']:>9}")
        else:
            print(f"{lab:<36}  -  not run yet")
    figure(rows, ROOT / "results" / "figures" / "paradigms.png", dwave_name is not None)
    slide_figure(rows, ROOT / "results" / "figures" / "paradigms_slide.png")
    print("wrote results/paradigms/summary.json, results/figures/paradigms.png and paradigms_slide.png")


def figure(rows, path, have_dwave):
    from run_benchmark import BG, COLOR, INK, MUTED, end_labels, style
    plt = style()
    sizes = sorted({r["qubits"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, metric, ylab in ((axes[0], "p_optimal", "Chance one shot is the best answer"),
                             (axes[1], "tre", "Map error of final answer (mm)")):
        labs = []
        for key, lab, _, ck in METHODS:
            xs, ys = [], []
            for q in sizes:
                v = [r[key][metric] for r in rows if r["qubits"] == q and r[key] is not None]
                if v:
                    xs.append(q); ys.append(np.mean(v))
            if not xs:
                continue
            ax.plot(xs, ys, color=COLOR[ck], marker="o", markeredgecolor=BG, markeredgewidth=2, label=lab)
            labs.append((xs[-1], ys[-1], lab.split(" (")[0], COLOR[ck]))
        if metric == "tre":
            for key, lab, ls in (("uncorrected", "No correction", (0, (4, 3))), ("best_possible", "Best possible", ":")):
                ys = [np.mean([r[key] for r in rows if r["qubits"] == q]) for q in sizes]
                ax.plot(sizes, ys, color=MUTED, ls=ls, lw=1.4)
                labs.append((sizes[-1], ys[-1], lab, MUTED))
        else:
            ax.set_yscale("log")
        ax.set_xticks(sizes); ax.set_xlim(sizes[0] - 0.5, sizes[-1] + 7)
        ax.set_xlabel("Qubits / variables"); ax.set_ylabel(ylab)
        ax._labs = labs
    title = "Classical vs gate-based quantum vs annealing, same patients"
    if have_dwave:
        title = "Classical vs gate-based quantum vs quantum annealing, same patients"
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=13, fontweight="bold")
    fig.tight_layout()
    for ax in axes:
        end_labels(ax, ax._labs)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def slide_figure(rows, path):
    """Big-type bar version for the deck: only the sizes every method was run on (fair comparison)."""
    from run_benchmark import BG, COLOR, INK, MUTED, style
    plt = style()
    plt.rcParams.update({"font.size": 15, "axes.titlesize": 17})
    keys = [k for k, *_ in METHODS if all(r[k] is not None for r in rows if r["ibm_qaoa"] is not None)
            and any(r[k] is not None for r in rows)]
    fair = [r for r in rows if r["ibm_qaoa"] is not None]
    plain = {"exact": "Normal computer:\nexact search", "sa": "Normal computer:\nannealing",
             "ibm_qaoa": "IBM quantum chip:\nlogic gates (QAOA)",
             "ibm_anneal": "IBM quantum chip:\nannealing, built from gates",
             "dwave": "D-Wave quantum\nannealer"}
    col = {k: COLOR[c] for k, _, _, c in METHODS}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.15, 1]})
    y = np.arange(len(keys))[::-1]
    p = [100 * np.mean([r[k]["p_optimal"] for r in fair]) for k in keys]
    a1.barh(y, p, color=[col[k] for k in keys], height=0.6, edgecolor=BG, linewidth=2)
    a1.set_xscale("log"); a1.set_xlim(0.1, 400)
    for yi, v in zip(y, p):
        a1.text(v * 1.15, yi, f"{v:.1f}%" if v < 10 else f"{v:.0f}%", va="center", color=INK, fontsize=15)
    a1.set_yticks(y); a1.set_yticklabels([plain[k] for k in keys], color=INK, fontsize=14)
    a1.set_xticks([0.1, 1, 10, 100]); a1.set_xticklabels(["0.1%", "1%", "10%", "100%"])
    a1.set_title("Tries that land on the best answer"); a1.grid(axis="y", visible=False)
    unc = np.mean([r["uncorrected"] for r in fair])
    keys2 = ["uncorrected"] + keys
    y2 = np.arange(len(keys2))[::-1]
    e = [unc] + [np.mean([r[k]["tre"] for r in fair]) for k in keys]
    a2.barh(y2, e, color=[MUTED] + [col[k] for k in keys], height=0.6, edgecolor=BG, linewidth=2)
    for yi, v in zip(y2, e):
        a2.text(v + 0.25, yi, f"{v:.1f} mm", va="center", color=INK, fontsize=15)
    a2.set_yticks(y2); a2.set_yticklabels(["No fix"] + [""] * len(keys), color=INK, fontsize=14)
    a2.set_xlim(0, unc * 1.25); a2.set_title("How far off the fixed map is (mm)"); a2.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
