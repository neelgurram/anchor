"""L5 — registration: turn trusted matches into a corrected brain map.

Warp = thin-plate spline fitted to the selected matches' displacement vectors
(MRI position -> ultrasound position). A TPS interpolates its control points exactly, so
a single wrong match drags the map toward the wrong spot: the tent-peg effect.

Headline metric: target registration error (TRE) on HELD-OUT landmarks, i.e. landmarks
the solver never saw, in native patient millimetres.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import RBFInterpolator

from .candidates import Problem
from .data import Case


# Mild TPS regularisation (an approximating spline, standard in landmark registration).
# Fixed 2026-11-05 before any benchmark sweep; it lowers error for every solver alike.
SMOOTHING = 100.0


class Warp:
    """Displacement field d(x) such that corrected position = x + d(x)."""

    def __init__(self, src: np.ndarray, dst: np.ndarray):
        self.src = np.asarray(src, float)
        disp = np.asarray(dst, float) - self.src
        self.n = len(self.src)
        if self.n >= 5:
            self.kind = "tps"
            self._f = RBFInterpolator(self.src, disp, kernel="thin_plate_spline", degree=1,
                                      smoothing=SMOOTHING)
        elif self.n >= 1:
            self.kind = "translation"           # too few points for a stable TPS
            self._t = disp.mean(axis=0)
        else:
            self.kind = "identity"

    def displacement(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, float))
        if self.kind == "tps":
            return self._f(x)
        if self.kind == "translation":
            return np.repeat(self._t[None], len(x), axis=0)
        return np.zeros_like(x)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, float))
        return x + self.displacement(x)


def warp_from_selection(problem: Problem, sel: np.ndarray) -> Warp:
    sel = np.asarray(sel, bool)
    return Warp(problem.cand_mri[sel], problem.cand_pos[sel])


def oracle_warp(case: Case, problem: Problem) -> Warp:
    """Best achievable with this landmark subset: TPS on the true pairs only."""
    return Warp(case.mri[problem.used_idx], case.us[problem.used_idx])


def reference_warp(case: Case) -> Warp:
    """Best estimate of the true shift field: TPS on ALL expert landmark pairs."""
    return Warp(case.mri, case.us)


def region_grid(case: Case, margin: float = 10.0, step: float = 4.0) -> np.ndarray:
    lo, hi = case.mri.min(0) - margin, case.mri.max(0) + margin
    axes = [np.arange(l, h + 1e-9, step) for l, h in zip(lo, hi)]
    g = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    # keep grid points within the landmark cloud's neighbourhood
    d = np.linalg.norm(g[:, None] - case.mri[None], axis=2).min(1)
    return g[d <= margin + 5.0]


@dataclass
class Evaluation:
    tre_uncorrected: float     # mean held-out error if the map is not updated
    tre: float                 # mean held-out error after this warp
    tre_max: float
    tre_oracle: float          # same landmark subset, true matches only
    map_error_max: float       # worst disagreement with the reference field over the region, mm
    map_error_mean: float
    n_selected: int
    precision: float
    recall: float
    warp_kind: str

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def evaluate(case: Case, problem: Problem, sel: np.ndarray, grid: np.ndarray | None = None) -> Evaluation:
    sel = np.asarray(sel, bool)
    w = warp_from_selection(problem, sel)
    held = problem.held_idx
    truth = case.us[held]
    err = np.linalg.norm(w(case.mri[held]) - truth, axis=1)
    unc = np.linalg.norm(case.mri[held] - truth, axis=1)
    orc = np.linalg.norm(oracle_warp(case, problem)(case.mri[held]) - truth, axis=1)
    g = region_grid(case) if grid is None else grid
    me = np.linalg.norm(w(g) - reference_warp(case)(g), axis=1)
    T = problem.cand_true
    tp = int((sel & T).sum())
    return Evaluation(
        tre_uncorrected=float(unc.mean()), tre=float(err.mean()), tre_max=float(err.max()),
        tre_oracle=float(orc.mean()), map_error_max=float(me.max()), map_error_mean=float(me.mean()),
        n_selected=int(sel.sum()), precision=tp / max(1, int(sel.sum())), recall=tp / max(1, int(T.sum())),
        warp_kind=w.kind,
    )
