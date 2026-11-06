"""L5b — confidence: where should the surgeon trust the corrected map, and when not at all?

A corrected map comes from one set of trusted matches. Two things can make it wrong:
  (a) a trusted match is itself wrong (the tent-peg problem), or
  (b) a region is supported by too few matches, so the warp there is a guess.

We never see the truth during surgery, so confidence is computed from the matches alone:

  * Hide-one check (leave-one-out cross-validation). Hide each trusted match in turn, fit
    the map to the others, and see where it predicts that landmark should be. A correct
    match lands near its prediction; a wrong one misses by millimetres to centimetres.
    The mean miss is the ESTIMATED map error; the alarm fires when it is too large.
  * Spread map. For every point on the brain: how far would the map move there if any
    single trusted match were dropped, or if one of the solver's other near-best answers
    were used instead? Small = blue (trust it), large = red (be careful here).

Alternatives come from the solver's own samples (simulated annealing, QAOA, digitized
annealing, QPU runs all return thousands of bitstrings). Single-answer solvers (exact,
naive, RANSAC) get the hide-one check only. Nothing here reads the ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .candidates import Problem
from .graph import repair_to_clique
from .registration import Warp, warp_from_selection

# Alarm rule (fixed before the validation sweep; the threshold is calibrated on half the
# patients and tested on the other half, see scripts/run_confidence.py):
MIN_TRUSTED = 5           # fewer trusted matches than this cannot support a non-rigid map
ALARM_MM = 3.0            # estimated error above this -> do not trust the update
MAX_ALTERNATIVES = 8
ALT_SLACK = 1.1           # an alternative may carry at most ~one match less weight


@dataclass
class Confidence:
    loo_miss: np.ndarray           # per trusted match (in selection order): hide-one miss, mm
    loo_index: np.ndarray          # candidate index of each trusted match
    est_error: float               # mean hide-one miss, mm (estimate of the map error)
    worst_index: int | None        # most suspicious trusted match
    worst_miss: float
    n_trusted: int
    n_alternatives: int
    alarm: bool
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "loo": [{"candidate": int(i), "miss_mm": round(float(m), 2)}
                    for i, m in zip(self.loo_index, self.loo_miss)],
            "est_error_mm": round(self.est_error, 2),
            "worst_candidate": self.worst_index, "worst_miss_mm": round(self.worst_miss, 2),
            "n_trusted": self.n_trusted, "n_alternatives": self.n_alternatives,
            "alarm": self.alarm, "reasons": self.reasons,
            "rule": {"min_trusted": MIN_TRUSTED, "alarm_mm": ALARM_MM},
        }


def hide_one(problem: Problem, sel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each trusted match: distance between where the OTHER trusted matches say it
    should be and where the matcher put it. Returns (candidate indices, misses in mm)."""
    idx = np.flatnonzero(sel)
    src, dst = problem.cand_mri, problem.cand_pos
    miss = np.zeros(len(idx))
    for t, i in enumerate(idx):
        rest = idx[idx != i]
        w = Warp(src[rest], dst[rest])
        miss[t] = float(np.linalg.norm(w(src[i])[0] - dst[i]))
    return idx, miss


def alternatives(adj: np.ndarray, w: np.ndarray, sel: np.ndarray, rows: np.ndarray | None,
                 energy: np.ndarray | None, max_rows: int = 300) -> list[np.ndarray]:
    """Distinct near-best consistent sets among the solver's samples (unique bitstrings
    `rows` with QUBO `energy`) that are NOT just a subset of the chosen set (those are
    already covered by the hide-one check)."""
    if rows is None or len(rows) == 0:
        return []
    rows = np.asarray(rows, bool)
    order = np.argsort(energy)[:max_rows]
    best_w = float(w[sel].sum())
    seen, out = {tuple(sel.astype(int))}, []
    for r in order:
        a = repair_to_clique(adj, rows[r], w)
        key = tuple(a.astype(int))
        if key in seen:
            continue
        seen.add(key)
        if w[a].sum() < best_w - ALT_SLACK or not (a & ~sel).any():
            continue
        out.append(a)
        if len(out) >= MAX_ALTERNATIVES:
            break
    return out


def members(sel: np.ndarray, alts: list[np.ndarray]) -> list[np.ndarray]:
    idx = np.flatnonzero(sel)
    out = []
    for i in idx:
        m = sel.copy()
        m[i] = False
        out.append(m)
    return out + list(alts)


def spread(problem: Problem, sel: np.ndarray, ens: list[np.ndarray], disp_fn) -> np.ndarray:
    """Per-point worst-case movement (mm) across the ensemble. `disp_fn(warp)` returns the
    displacement of the points of interest (surface vertices, or held-out landmarks)."""
    base = disp_fn(warp_from_selection(problem, sel))
    out = np.zeros(len(base))
    for m in ens:
        d = np.linalg.norm(disp_fn(warp_from_selection(problem, m)) - base, axis=1)
        np.maximum(out, d, out=out)
    return out


def assess(problem: Problem, sel: np.ndarray, n_alternatives: int = 0,
           alarm_mm: float = ALARM_MM) -> Confidence:
    sel = np.asarray(sel, bool)
    idx, miss = hide_one(problem, sel)
    est = float(miss.mean()) if len(miss) else float("inf")
    reasons = []
    if len(idx) < MIN_TRUSTED:
        reasons.append(f"only {len(idx)} trusted matches; at least {MIN_TRUSTED} are needed")
    if est > alarm_mm:
        reasons.append(f"hidden matches are missed by {est:.1f} mm on average (limit {alarm_mm:.0f} mm)")
    wi = int(np.argmax(miss)) if len(miss) else None
    return Confidence(
        loo_miss=miss, loo_index=idx, est_error=est,
        worst_index=None if wi is None else int(idx[wi]),
        worst_miss=0.0 if wi is None else float(miss[wi]),
        n_trusted=int(len(idx)), n_alternatives=n_alternatives,
        alarm=bool(reasons), reasons=reasons,
    )
