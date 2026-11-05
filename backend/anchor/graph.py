"""L2 — consistency graph.

Node = candidate match. Two matches are connected when they are for different MRI
landmarks AND they preserve distance: if landmarks i and j are d mm apart in the MRI,
their ultrasound partners should still be about d mm apart. Brain shift moves tissue a
lot (RESECT mean 5.4 mm, up to 21 mm) but mostly as a coherent block, so pairwise
distances between true matches change little (RESECT: median 0.8 mm, 95th pct ~2.3 mm).

The largest set of mutually connected nodes (maximum clique) is the largest set of
mutually consistent matches.
"""
from __future__ import annotations

import numpy as np

from .candidates import Problem

# Tolerance: |d_MRI - d_US| <= TAU_MM + TAU_REL * d_MRI. Fixed in CHARTER.md from the
# geometry of the RESECT landmarks alone (no solver output), before any quantum run.
# Non-rigid stretch grows with distance, hence the relative term.
TAU_MM = 2.5
TAU_REL = 0.03


def _dists(problem: Problem) -> tuple[np.ndarray, np.ndarray]:
    a, b = problem.cand_mri, problem.cand_pos
    return (np.linalg.norm(a[:, None] - a[None], axis=2),
            np.linalg.norm(b[:, None] - b[None], axis=2))


def pairwise_dd(problem: Problem) -> np.ndarray:
    d_mri, d_us = _dists(problem)
    return np.abs(d_mri - d_us)


def consistency_graph(problem: Problem, tau: float = TAU_MM, tau_rel: float = TAU_REL) -> np.ndarray:
    """Symmetric boolean adjacency (m, m), no self loops."""
    d_mri, d_us = _dists(problem)
    same = problem.cand_landmark[:, None] == problem.cand_landmark[None]
    adj = (np.abs(d_mri - d_us) <= tau + tau_rel * d_mri) & ~same
    np.fill_diagonal(adj, False)
    return adj


def is_clique(adj: np.ndarray, sel: np.ndarray) -> bool:
    idx = np.flatnonzero(sel)
    if len(idx) < 2:
        return True
    sub = adj[np.ix_(idx, idx)]
    return bool(sub[np.triu_indices(len(idx), 1)].all())


def repair_to_clique(adj: np.ndarray, sel: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Greedy post-processing: drop the node with the most conflicts (ties: lowest weight)
    until the selection is a clique. Standard for sampled QUBO solutions."""
    sel = sel.astype(bool).copy()
    while not is_clique(adj, sel):
        idx = np.flatnonzero(sel)
        sub = adj[np.ix_(idx, idx)]
        conflicts = (~sub).sum(axis=1) - 1          # minus self (diagonal is False)
        worst = max(range(len(idx)), key=lambda t: (conflicts[t], -weights[idx[t]]))
        sel[idx[worst]] = False
    return sel
