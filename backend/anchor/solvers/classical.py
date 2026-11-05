"""Classical baselines: naive, RANSAC, exact maximum clique, simulated annealing."""
from __future__ import annotations

import time

import numpy as np

from ..graph import TAU_MM, TAU_REL, is_clique
from ..qubo import energy
from . import Instance, SolveResult, summarise_samples


def _single(inst: Instance, solver: str, sel: np.ndarray, t0: float, **prov) -> SolveResult:
    sel = np.asarray(sel, bool)
    clique = is_clique(inst.adj, sel)
    prov["is_clique"] = clique
    return SolveResult(
        solver=solver, selection=sel, raw_best=sel, repaired=False,
        best_energy=energy(inst.Q, sel),
        # approximation ratio is only defined for valid (consistent) selections
        approx_ratio=float(inst.w[sel].sum() / inst.opt_weight) if clique else None,
        p_optimal=None, p_feasible=None, expected_ratio=None,
        wall_time=time.perf_counter() - t0, provenance=prov,
    )


def solve_naive(inst: Instance, **_) -> SolveResult:
    """Trust each landmark's best-scoring candidate. What a plain matcher does; no consistency check."""
    t0 = time.perf_counter()
    p = inst.problem
    sel = np.zeros(inst.m, bool)
    for li in range(p.n_used):
        idx = np.flatnonzero(p.cand_landmark == li)
        sel[idx[np.argmax(p.cand_score[idx])]] = True
    return _single(inst, "naive", sel, t0, method="argmax score per landmark")


def solve_exact(inst: Instance, **_) -> SolveResult:
    """Exact maximum-weight clique (enumerates maximal cliques, networkx)."""
    t0 = time.perf_counter()
    from ..qubo import max_weight_clique
    sel, _ = max_weight_clique(inst.adj, inst.w)
    return _single(inst, "exact", sel, t0, method="networkx find_cliques (exact)")


def _kabsch(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rigid R, t minimising ||R a + t - b||."""
    ca, cb = a.mean(0), b.mean(0)
    H = (a - ca).T @ (b - cb)
    U, _, Vt = np.linalg.svd(H)
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, cb - R @ ca


def solve_ransac(inst: Instance, iters: int = 500, seed: int = 0, **_) -> SolveResult:
    """Standard robust-registration baseline: fit a rigid transform to random 3-match samples,
    keep the hypothesis with the most inliers (one per landmark, within the same tolerance)."""
    t0 = time.perf_counter()
    p = inst.problem
    rng = np.random.default_rng(seed)
    A, B, L = p.cand_mri, p.cand_pos, p.cand_landmark
    thr = TAU_MM + TAU_REL * 20.0                 # tolerance at a typical 20 mm landmark spacing
    best_sel, best_key = np.zeros(inst.m, bool), (-1, -np.inf)
    for _ in range(iters):
        lms = rng.choice(p.n_used, size=3, replace=False)
        pick = [rng.choice(np.flatnonzero(L == li)) for li in lms]
        R, t = _kabsch(A[pick], B[pick])
        res = np.linalg.norm(A @ R.T + t - B, axis=1)
        sel = np.zeros(inst.m, bool)
        for li in range(p.n_used):
            idx = np.flatnonzero(L == li)
            j = idx[np.argmin(res[idx])]
            if res[j] <= thr:
                sel[j] = True
        key = (int(sel.sum()), -float(res[sel].sum()))
        if key > best_key:
            best_key, best_sel = key, sel
    return _single(inst, "ransac", best_sel, t0, method=f"RANSAC rigid, {iters} iters, thr {thr:.1f} mm")


def solve_sa(inst: Instance, num_reads: int = 200, seed: int = 0, **_) -> SolveResult:
    """Simulated annealing on the same QUBO (classical; dwave-samplers)."""
    import dimod
    from dwave.samplers import SimulatedAnnealingSampler
    t0 = time.perf_counter()
    m = inst.m
    Q = {(i, j): inst.Q[i, j] for i in range(m) for j in range(i, m) if inst.Q[i, j] != 0}
    bqm = dimod.BinaryQuadraticModel.from_qubo(Q)
    ss = SimulatedAnnealingSampler().sample(bqm, num_reads=num_reads, seed=seed).aggregate()
    X = np.array([[s.get(i, 0) for i in range(m)] for s in ss.samples()], dtype=bool)
    counts = np.asarray(ss.record.num_occurrences)
    return summarise_samples(inst, X, counts, "sa", time.perf_counter() - t0,
                             provenance={"method": "dwave-samplers SimulatedAnnealingSampler",
                                         "num_reads": num_reads, "seed": seed})
