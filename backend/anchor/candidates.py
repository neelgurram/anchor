"""L1 — candidate matches.

A real navigation system would run a feature matcher between the pre-op MRI and the
intra-op ultrasound. That matcher is out of scope here; instead we simulate its output
honestly: for every MRI landmark we emit the true ultrasound partner (with ~0.5 mm
localisation jitter) plus k-1 decoys of two kinds seen in practice:

  * "swap"    — the matcher latches onto a different, similar-looking landmark
  * "speckle" — the matcher latches onto ultrasound speckle 4-15 mm away

Each candidate carries a similarity score. With probability `outlier_rate` a decoy
outscores the true partner for that landmark, which is exactly what makes a naive
"trust the best-scoring match" policy fail.

Landmarks not used for matching are held out and only used to measure error.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .data import Case

JITTER_MM = 0.5
SPECKLE_MM = (4.0, 15.0)


@dataclass
class Problem:
    case_id: str
    seed: int
    n_used: int
    k: int
    outlier_rate: float
    used_idx: np.ndarray          # (n_used,) indices into the case's landmarks
    held_idx: np.ndarray          # held-out landmark indices (error measurement only)
    mri_used: np.ndarray          # (n_used, 3) mm
    cand_landmark: np.ndarray     # (m,) which used landmark (0..n_used-1) each candidate is for
    cand_pos: np.ndarray          # (m, 3) candidate ultrasound position, mm
    cand_true: np.ndarray         # (m,) bool, ground truth (never shown to solvers)
    cand_score: np.ndarray        # (m,) matcher similarity score in [0, 1]
    cand_kind: list = field(default_factory=list)   # "true" | "swap" | "speckle"

    @property
    def m(self) -> int:
        return len(self.cand_pos)

    @property
    def cand_mri(self) -> np.ndarray:
        """MRI position of the landmark each candidate claims to match."""
        return self.mri_used[self.cand_landmark]


def _unit(rng: np.random.Generator) -> np.ndarray:
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def make_problem(case: Case, n_used: int = 8, k: int = 2, outlier_rate: float = 0.25,
                 seed: int = 0) -> Problem:
    if not 3 <= n_used <= case.n:
        raise ValueError(f"n_used must be in [3, {case.n}]")
    if k < 1:
        raise ValueError("k must be >= 1")
    rng = np.random.default_rng(seed)
    order = rng.permutation(case.n)
    used, held = np.sort(order[:n_used]), np.sort(order[n_used:])

    lm, pos, true, score, kind = [], [], [], [], []
    for li, gi in enumerate(used):
        t_score = rng.uniform(0.6, 1.0)
        lm.append(li); pos.append(case.us[gi] + rng.normal(0, JITTER_MM, 3))
        true.append(True); score.append(t_score); kind.append("true")
        others = [j for j in used if j != gi]
        flipped = rng.random() < outlier_rate
        for d in range(k - 1):
            if others and rng.random() < 0.5:
                j = rng.choice(others)
                p, kd = case.us[j] + rng.normal(0, JITTER_MM, 3), "swap"
            else:
                p, kd = case.us[gi] + _unit(rng) * rng.uniform(*SPECKLE_MM), "speckle"
            s = rng.uniform(0.2, 0.7)
            if flipped and d == 0:                      # this decoy beats the true match
                s = min(1.0, t_score + rng.uniform(0.05, 0.2))
            lm.append(li); pos.append(p); true.append(False); score.append(s); kind.append(kd)

    perm = rng.permutation(len(pos))                    # don't let qubit order leak the answer
    return Problem(
        case_id=case.case_id, seed=seed, n_used=n_used, k=k, outlier_rate=outlier_rate,
        used_idx=used, held_idx=held, mri_used=case.mri[used],
        cand_landmark=np.asarray(lm)[perm], cand_pos=np.asarray(pos)[perm],
        cand_true=np.asarray(true)[perm], cand_score=np.asarray(score)[perm],
        cand_kind=[kind[i] for i in perm],
    )
