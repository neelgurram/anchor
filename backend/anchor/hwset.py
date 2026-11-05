"""The fixed instance set shared by the noise-model study and the IBM / D-Wave hardware runs,
so ideal simulator, noisy simulator and real hardware are compared on identical problems."""
from __future__ import annotations

from .candidates import make_problem
from .data import load_case
from .solvers import make_instance

OUTLIER = 0.3
K = 2
# (case, seed) pairs where trusting the top match visibly fails at these sizes
CASES = [("Case12", 9), ("Case2", 2)]
GATE_SIZES = [3, 4, 5, 6]            # landmarks -> 6, 8, 10, 12 qubits (IBM)
ANNEAL_SIZES = [3, 4, 5, 6, 8, 10, 12]  # up to 24 variables (D-Wave embeds these easily)


def problem_params(case_id: str, n_used: int, seed: int) -> dict:
    return {"case_id": case_id, "n_used": n_used, "k": K, "outlier_rate": OUTLIER, "seed": seed}


def build(case_id: str, n_used: int, seed: int):
    case = load_case(case_id)
    prob = make_problem(case, n_used=n_used, k=K, outlier_rate=OUTLIER, seed=seed)
    return case, prob, make_instance(prob)


def gate_set():
    return [(c, n, s) for c, s in CASES for n in GATE_SIZES]


def anneal_set():
    return [(c, n, s) for c, s in CASES for n in ANNEAL_SIZES]
