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


def gate_modes(inst, seed: int) -> dict:
    """Circuits sent to IBM, all fixed on the IDEAL simulator before any hardware or noise run:
    QAOA p=1 (optimised angles), and the linear-ramp anneal at a shallow (p=2) and a deep
    (best of p=3,5) schedule — the noise study showed depth is the deciding factor on Heron."""
    import numpy as np
    from .solvers.quantum import lr_params, solve_qaoa, tune_anneal
    q1 = solve_qaoa(inst, p=1, shots=2048, maxiter=60, seed=seed, with_device_stats=False)
    _, d_sh = tune_anneal(inst.Q, ps=(2,), seed=seed)
    p_dp, d_dp = tune_anneal(inst.Q, ps=(3, 5), seed=seed)
    return {
        "qaoa_p1": {"label": "QAOA p=1", "layers": 1, "params": np.array(q1.provenance["params"]),
                    "family": "variational"},
        "anneal_shallow": {"label": "Digitized anneal p=2", "layers": 2, "params": lr_params(2, d_sh),
                           "delta": d_sh, "family": "linear-ramp (LR-QAOA)"},
        "anneal_deep": {"label": f"Digitized anneal p={p_dp}", "layers": p_dp, "params": lr_params(p_dp, d_dp),
                        "delta": d_dp, "family": "linear-ramp (LR-QAOA)"},
    }
