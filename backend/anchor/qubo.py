"""L3 — maximum-weight-clique QUBO.

    minimise  E(x) = -Σ_i w_i x_i  +  P · Σ_{i<j, (i,j) not an edge} x_i x_j,   x ∈ {0,1}^m

w_i = 1 + λ·score_i (λ small, so clique SIZE always dominates and the matcher's score
only breaks ties). Choosing P > max(w) guarantees every optimum is a clique: dropping one
endpoint of a violated pair loses at most max(w) and saves at least P.

Convention: Q is upper-triangular, E(x) = x^T Q x (diagonal = linear terms).
"""
from __future__ import annotations

import itertools

import networkx as nx
import numpy as np

from .candidates import Problem

LAMBDA = 0.05


def weights(problem: Problem, lam: float = LAMBDA) -> np.ndarray:
    return 1.0 + lam * problem.cand_score


def build_qubo(adj: np.ndarray, w: np.ndarray, penalty: float | None = None) -> np.ndarray:
    m = len(w)
    P = 2.0 * float(w.max()) if penalty is None else float(penalty)
    Q = np.zeros((m, m))
    Q[np.diag_indices(m)] = -w
    iu = np.triu_indices(m, 1)
    non_edge = ~adj[iu]
    Q[iu[0][non_edge], iu[1][non_edge]] = P
    return Q


def energy(Q: np.ndarray, x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    return float(x @ Q @ x)


def energies(Q: np.ndarray, X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    return np.einsum("ni,ij,nj->n", X, Q, X)


def n_terms(Q: np.ndarray) -> dict:
    iu = np.triu_indices(len(Q), 1)
    return {"linear": int(np.count_nonzero(np.diag(Q))), "quadratic": int(np.count_nonzero(Q[iu]))}


def max_weight_clique(adj: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """Exact: with positive weights the optimum is a maximal clique, so enumerate them."""
    g = nx.from_numpy_array(adj.astype(int))
    best, best_w = [], -1.0
    for c in nx.find_cliques(g):
        cw = float(w[c].sum())
        if cw > best_w + 1e-12:
            best, best_w = c, cw
    x = np.zeros(len(w), dtype=bool)
    x[best] = True
    return x, best_w


def brute_force(Q: np.ndarray) -> tuple[np.ndarray, float]:
    """All 2^m states — only for validation on small instances (m <= 20)."""
    m = len(Q)
    if m > 20:
        raise ValueError("brute force limited to 20 variables")
    X = np.array(list(itertools.product([0, 1], repeat=m)), dtype=float)
    E = energies(Q, X)
    i = int(E.argmin())
    return X[i].astype(bool), float(E[i])


def to_ising(Q: np.ndarray):
    """QUBO -> Ising SparsePauliOp (coefficients normalised to max |c| = 1) + offset.
    x_i = (1 - z_i) / 2. Adapted from Q-Router's qubo_to_ising."""
    from qiskit.quantum_info import SparsePauliOp
    n = len(Q)
    h = np.zeros(n)
    terms, offset = [], 0.0
    for i in range(n):
        h[i] -= Q[i, i] / 2
        offset += Q[i, i] / 2
        for j in range(i + 1, n):
            if Q[i, j] != 0:
                terms.append(("ZZ", [i, j], Q[i, j] / 4))
                h[i] -= Q[i, j] / 4
                h[j] -= Q[i, j] / 4
                offset += Q[i, j] / 4
    terms += [("Z", [i], h[i]) for i in range(n) if abs(h[i]) > 1e-12]
    H = SparsePauliOp.from_sparse_list(terms, num_qubits=n).simplify()
    scale = float(np.abs(H.coeffs).max())
    return SparsePauliOp(H.paulis, H.coeffs / scale), offset, scale
