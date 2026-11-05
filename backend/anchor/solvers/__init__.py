"""L4 — solvers. Every solver takes a `Instance` and returns a `SolveResult`."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..candidates import Problem
from ..graph import consistency_graph, is_clique, repair_to_clique
from ..qubo import build_qubo, energies, max_weight_clique, n_terms, weights


@dataclass
class Instance:
    """Everything a solver may see. Ground truth (problem.cand_true) is NOT used by solvers."""
    problem: Problem
    adj: np.ndarray
    w: np.ndarray
    Q: np.ndarray
    opt_x: np.ndarray
    opt_weight: float

    @property
    def m(self) -> int:
        return len(self.w)

    @property
    def opt_energy(self) -> float:
        return -self.opt_weight


def make_instance(problem: Problem) -> Instance:
    adj = consistency_graph(problem)
    w = weights(problem)
    Q = build_qubo(adj, w)
    opt_x, opt_w = max_weight_clique(adj, w)
    return Instance(problem, adj, w, Q, opt_x, opt_w)


@dataclass
class SolveResult:
    solver: str
    selection: np.ndarray                 # final trusted matches (bool, length m), always a clique
                                          # except for the naive baseline
    raw_best: np.ndarray                  # lowest-energy raw sample before repair
    repaired: bool
    best_energy: float
    approx_ratio: float | None            # weight(selection) / optimum weight (0..1); None if the
                                          # selection is not a consistent set (naive / RANSAC)
    p_optimal: float | None               # fraction of samples that are optimal (sampling solvers)
    p_feasible: float | None              # fraction of samples that are cliques
    expected_ratio: float | None          # mean over samples of max(0, -E) / opt weight
    wall_time: float
    qpu_time: float | None = None
    samples: list = field(default_factory=list)   # top samples: {"bits": [...], "count": n, "energy": e}
    circuit: dict | None = None
    provenance: dict = field(default_factory=dict)
    replay: bool = False

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        for k in ("selection", "raw_best"):
            d[k] = [int(v) for v in np.asarray(d[k]).astype(int)]
        return d


def summarise_samples(inst: Instance, X: np.ndarray, counts: np.ndarray, solver: str,
                      wall_time: float, top: int = 12, **extra) -> SolveResult:
    """Common scoring for any solver that returns a distribution of bitstrings."""
    X = np.asarray(X, dtype=bool)
    counts = np.asarray(counts, dtype=float)
    E = energies(inst.Q, X)
    total = counts.sum()
    opt = np.isclose(E, inst.opt_energy, atol=1e-9)
    feas = np.array([is_clique(inst.adj, x) for x in X])
    best_i = int(E.argmin())
    raw = X[best_i]
    sel = repair_to_clique(inst.adj, raw, inst.w)
    order = np.argsort(E)[:top]
    samples = [{"bits": [int(b) for b in X[i]], "count": int(counts[i]), "energy": round(float(E[i]), 4)}
               for i in order]
    return SolveResult(
        solver=solver, selection=sel, raw_best=raw, repaired=bool((sel != raw).any()),
        best_energy=float(E[best_i]), approx_ratio=float(inst.w[sel].sum() / inst.opt_weight),
        p_optimal=float(counts[opt].sum() / total), p_feasible=float(counts[feas].sum() / total),
        expected_ratio=float((np.maximum(0, -E) * counts).sum() / total / inst.opt_weight),
        wall_time=wall_time, samples=samples, **extra,
    )
