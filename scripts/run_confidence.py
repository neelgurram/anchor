"""Validate the confidence map and alarm (anchor/confidence.py) against the truth.

The confidence engine never sees the truth. Here we check it against the truth:
  1. Does the ESTIMATED map error (hide-one check) track the REAL error at held-out
     expert landmarks?
  2. Does the ALARM fire on bad maps (real error > 3 mm) and stay quiet on good ones?
     The alarm threshold is calibrated on even-numbered patients and tested on
     odd-numbered patients, so the reported accuracy is on patients it was not tuned on.
  3. Does the per-point SPREAD (the colour on the brain) track the real error at that
     point? Measured at held-out landmarks, where the truth is known.

    python scripts/run_confidence.py        -> results/confidence/summary.json, rows.csv,
                                               results/figures/confidence.png
"""
from __future__ import annotations

import csv
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402

OUT = ROOT / "results" / "confidence"
FIG = ROOT / "results" / "figures"
BAD_MM = 3.0                   # a corrected map worse than this at held-out landmarks is "bad"
CLASSICAL = ["naive", "ransac", "exact", "sa"]
QUANTUM = ["danneal", "qaoa"]


def job(task):
    from anchor import confidence as C
    from anchor.candidates import make_problem
    from anchor.data import load_case
    from anchor.registration import warp_from_selection
    from anchor.solvers import make_instance
    from anchor.solvers.registry import LIVE

    case = load_case(task["case_id"])
    n_used = min(task["n_used"], case.n - 3)
    p = make_problem(case, n_used=n_used, k=2, outlier_rate=task["outlier_rate"], seed=task["seed"])
    inst = make_instance(p)
    held_mri, held_us = case.mri[p.held_idx], case.us[p.held_idx]
    rows, points = [], []
    for s in task["solvers"]:
        kw = {"with_device_stats": False} if s in QUANTUM else {}
        r = LIVE[s](inst, seed=task["seed"], **kw)
        sel = r.selection
        alts = [np.asarray(a, bool) for a in r.alternatives]
        cf = C.assess(p, sel, len(alts))
        err = np.linalg.norm(warp_from_selection(p, sel)(held_mri) - held_us, axis=1)
        sp_all = C.spread(p, sel, C.members(sel, alts), lambda w: w.displacement(held_mri))
        sp_loo = C.spread(p, sel, C.members(sel, []), lambda w: w.displacement(held_mri))
        rows.append({"case_id": case.case_id, "case_num": int(case.case_id[4:]), "n_used": n_used,
                     "qubits": inst.m, "outlier_rate": task["outlier_rate"], "seed": task["seed"],
                     "solver": s, "tre": float(err.mean()), "est_error": cf.est_error,
                     "n_trusted": cf.n_trusted, "n_alternatives": len(alts),
                     "precision": float((sel & p.cand_true).sum() / max(1, sel.sum())),
                     "worst_miss": cf.worst_miss,
                     "worst_is_wrong": None if cf.worst_index is None else bool(not p.cand_true[cf.worst_index]),
                     "has_wrong": bool((sel & ~p.cand_true).any())})
        for e, a, b in zip(err, sp_all, sp_loo):
            points.append({"solver": s, "err": float(e), "spread": float(a), "spread_loo": float(b)})
    return rows, points


def spearman(a, b):
    from scipy.stats import spearmanr
    return float(spearmanr(a, b).statistic)


def alarm_stats(rows, thr):
    bad = np.array([r["tre"] > BAD_MM for r in rows])
    from anchor.confidence import MIN_TRUSTED
    al = np.array([(r["est_error"] > thr) or (r["n_trusted"] < MIN_TRUSTED) for r in rows])
    tp, fn = int((al & bad).sum()), int((~al & bad).sum())
    fp, tn = int((al & ~bad).sum()), int((~al & ~bad).sum())
    return {"threshold_mm": thr, "bad_maps": int(bad.sum()), "good_maps": int((~bad).sum()),
            "caught": tp, "missed": fn, "false_alarms": fp, "quiet_ok": tn,
            "sensitivity": tp / max(1, tp + fn), "specificity": tn / max(1, tn + fp),
            "balanced_accuracy": 0.5 * (tp / max(1, tp + fn) + tn / max(1, tn + fp))}


def figure(rows, points, thr, path):
    from run_benchmark import BG, COLOR, INK, MUTED, SHORT, style
    plt = style()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})

    # left: estimated vs real map error, per instance
    order = ["naive", "ransac", "exact", "sa", "danneal", "qaoa"]
    for s in order:
        rr = [r for r in rows if r["solver"] == s]
        if not rr:
            continue
        x = np.array([r["est_error"] for r in rr]); y = np.array([r["tre"] for r in rr])
        a1.scatter(np.clip(x, 0.3, 60), np.clip(y, 0.3, 60), s=12, color=COLOR[s], alpha=0.55,
                   edgecolors="none", label=SHORT[s])
    a1.set_xscale("log"); a1.set_yscale("log")
    lim = (0.4, 60)
    a1.plot(lim, lim, color=MUTED, lw=1, ls=(0, (2, 3)))
    a1.axvline(thr, color=INK, lw=1.2)
    a1.axhline(BAD_MM, color=MUTED, lw=1, ls=(0, (4, 3)))
    a1.text(thr * 1.07, 0.45, f"alarm above {thr:g} mm", color=INK, fontsize=9)
    a1.text(0.45, BAD_MM * 1.08, f"bad map (> {BAD_MM:.0f} mm)", color=MUTED, fontsize=9)
    a1.set_xlim(*lim); a1.set_ylim(*lim)
    a1.set_xlabel("Estimated error from the matches alone (hide-one check, mm)")
    a1.set_ylabel("Real error at hidden expert landmarks (mm)")
    rho = spearman([r["est_error"] for r in rows], [r["tre"] for r in rows])
    a1.set_title(f"Anchor's estimate rises with the real error (Spearman ρ = {rho:.2f})")
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    for axis in (a1.xaxis, a1.yaxis):
        axis.set_major_locator(FixedLocator([0.5, 1, 3, 10, 30]))
        axis.set_minor_locator(NullLocator())
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    a1.legend(loc="upper left", fontsize=8.5, ncol=2, markerscale=1.6)

    # right: real error by colour band of the confidence map
    bands = [(0, 1, "< 1 mm"), (1, 2, "1–2"), (2, 3, "2–3"), (3, 5, "3–5"), (5, 1e9, "> 5 mm")]
    sp = np.array([q["spread"] for q in points]); er = np.array([q["err"] for q in points])
    med, p90, n = [], [], []
    for lo, hi, _ in bands:
        m = (sp >= lo) & (sp < hi)
        n.append(int(m.sum()))
        med.append(np.median(er[m]) if m.any() else np.nan)
        p90.append(np.percentile(er[m], 90) if m.any() else np.nan)
    xs = np.arange(len(bands))
    band_col = ["#2b6cff", "#19d3c5", "#8cda89", "#ffb03f", "#ff3b3b"]   # same colour scale as the app
    a2.bar(xs, med, width=0.6, color=band_col, edgecolor=BG, linewidth=2)
    a2.scatter(xs, p90, marker="_", s=320, color=INK, linewidths=2, zorder=3, label="90th percentile")
    for x, m, k in zip(xs, med, n):
        if not np.isnan(m):
            a2.text(x, m * 1.12 + 0.05, f"{m:.1f} mm", ha="center", color=INK, fontsize=9.5)
            a2.text(x, 0.3, f"n = {k:,}", ha="center", color=BG, fontsize=8.5, fontweight="bold")
    a2.set_yscale("log"); a2.set_ylim(0.25, max(np.nanmax(p90) * 1.6, 10))
    a2.yaxis.set_major_locator(FixedLocator([0.5, 1, 2, 5, 10]))
    a2.yaxis.set_minor_locator(NullLocator())
    a2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    a2.set_xticks(xs, [b[2] for b in bands])
    a2.set_xlabel("Confidence-map value at that point (spread, mm)")
    a2.set_ylabel("Real error at that point (median, mm)")
    a2.set_title("Redder points on the map are less accurate")
    a2.legend(loc="upper left", fontsize=9)
    a2.grid(axis="x", visible=False)
    fig.text(0.01, 0.01, f"{len(rows)} corrected maps, 22 RESECT patients; right panel: {len(points)} hidden expert "
             "landmarks. Nothing in the confidence engine sees the truth.", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    from anchor.data import list_cases
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = []
    for cid in list_cases():
        for n in (6, 8, 10, 12):
            for o in (0.0, 0.2, 0.4):
                for seed in range(3):
                    tasks.append({"case_id": cid, "n_used": n, "outlier_rate": o, "seed": seed, "solvers": CLASSICAL})
        for n in (6, 8):
            for o in (0.2, 0.4):
                tasks.append({"case_id": cid, "n_used": n, "outlier_rate": o, "seed": 100, "solvers": QUANTUM})
    t0 = time.time()
    rows, points = [], []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 2)) as ex:
        for r, q in ex.map(job, tasks, chunksize=4):
            rows += r; points += q
    print(f"{len(rows)} maps, {len(points)} points, {time.time() - t0:.0f}s")

    with open(OUT / "rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    calib = [r for r in rows if r["case_num"] % 2 == 0]
    test = [r for r in rows if r["case_num"] % 2 == 1]
    grid = np.round(np.arange(1.5, 8.01, 0.25), 2)
    best = max(grid, key=lambda t: (alarm_stats(calib, t)["balanced_accuracy"], -t))
    sp = np.array([q["spread"] for q in points]); er = np.array([q["err"] for q in points])
    spl = np.array([q["spread_loo"] for q in points])
    by_solver = {}
    for s in CLASSICAL + QUANTUM:
        rr = [r for r in rows if r["solver"] == s]
        tt = [r for r in test if r["solver"] == s]
        by_solver[s] = {"maps": len(rr), "mean_est_error": float(np.mean([r["est_error"] for r in rr])),
                        "mean_tre": float(np.mean([r["tre"] for r in rr])),
                        "alarm_rate": float(np.mean([(r["est_error"] > best) or (r["n_trusted"] < 5) for r in rr])),
                        "test": alarm_stats(tt, float(best)) if tt else None}
    wrong = [r for r in rows if r["has_wrong"] and r["worst_is_wrong"] is not None]
    summary = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "bad_map_mm": BAD_MM,
        "n_maps": len(rows), "n_points": len(points),
        "estimate_vs_real_spearman": spearman([r["est_error"] for r in rows], [r["tre"] for r in rows]),
        "alarm": {"calibrated_on": "even-numbered patients", "tested_on": "odd-numbered patients",
                  "threshold_mm": float(best),
                  "calibration": alarm_stats(calib, float(best)),
                  "test": alarm_stats(test, float(best)),
                  "test_at_prefixed_3mm": alarm_stats(test, 3.0)},
        "spread_vs_real_spearman": spearman(sp, er),
        "spread_vs_real_spearman_hide_one_only": spearman(spl, er),
        "points_red_vs_blue": {"real_error_median_where_spread_lt_1mm": float(np.median(er[sp < 1])) if (sp < 1).any() else None,
                               "real_error_median_where_spread_gt_5mm": float(np.median(er[sp > 5])) if (sp > 5).any() else None},
        "worst_match_is_a_wrong_match": {"maps_with_a_wrong_trusted_match": len(wrong),
                                         "fraction_flagged_correctly": float(np.mean([r["worst_is_wrong"] for r in wrong])) if wrong else None},
        "by_solver": by_solver,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    FIG.mkdir(parents=True, exist_ok=True)
    figure(rows, points, float(best), FIG / "confidence.png")
    print(json.dumps({k: summary[k] for k in ("estimate_vs_real_spearman", "alarm", "spread_vs_real_spearman",
                                              "spread_vs_real_spearman_hide_one_only", "points_red_vs_blue",
                                              "worst_match_is_a_wrong_match")}, indent=1))
    for s, v in by_solver.items():
        print(s, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items() if k != "test"},
              "test:", {k: round(v["test"][k], 3) for k in ("sensitivity", "specificity")} if v["test"] else None)


if __name__ == "__main__":
    main()
