"""Gate-based quantum solvers (Qiskit).

* qaoa    — variational QAOA: p layers, angles tuned by COBYLA on a CVaR objective,
            started from an annealing-like schedule.
* danneal — digitized quantum annealing on gate hardware (linear-ramp QAOA, "LR-QAOA"):
            the slow sweep from the mixer to the problem Hamiltonian chopped into p
            Trotter steps with a FIXED schedule — no classical optimizer loop.

Both run locally on Aer (live in the app) and, via scripts/run_hardware.py, on IBM
hardware. Sign conventions and the Aer batching caveat follow Q-Router
(C:/Users/gurra/Projects/q-router-gh/q_router.py), which validated them on ibm_kingston.
"""
from __future__ import annotations

import time
from functools import lru_cache

import numpy as np
from scipy.optimize import minimize

from ..qubo import energies, to_ising
from . import Instance, SolveResult, summarise_samples


def bits_to_x(b: str) -> np.ndarray:
    """Qiskit bitstrings are little-endian: qubit 0 is the RIGHTMOST character."""
    return np.array([c == "1" for c in b[::-1]], dtype=bool)


def counts_to_arrays(counts: dict) -> tuple[np.ndarray, np.ndarray]:
    keys = list(counts)
    return np.array([bits_to_x(k) for k in keys]), np.array([counts[k] for k in keys], float)


def annealing_init(p: int, scale: float = 0.6) -> np.ndarray:
    """β ramps down, |γ| ramps up. γ < 0: QAOAAnsatz starts in |+>, the TOP state of its ΣX
    mixer, so opposite signs make the sweep track the LOWEST energy (Q-Router note)."""
    t = (np.arange(p) + 0.5) / p
    return np.concatenate([scale * (1 - t), -scale * t])


def lr_params(p: int, delta: float = 0.6) -> np.ndarray:
    i = np.arange(p)
    return np.concatenate([(1 - i / p) * delta, -(i + 1) / p * delta])


def build_circuit(Q: np.ndarray, p: int):
    from qiskit.circuit.library import QAOAAnsatz
    H, _, _ = to_ising(Q)
    qc = QAOAAnsatz(H, reps=p)
    qc.measure_all()
    return qc


_SIM = None


def local_sampler():
    global _SIM
    if _SIM is None:
        from qiskit_aer import AerSimulator
        from qiskit_aer.primitives import SamplerV2
        _SIM = (AerSimulator(method="statevector"), SamplerV2)
    return _SIM


def run_local(Q: np.ndarray, p: int, params: np.ndarray, shots: int = 2048, seed: int = 0) -> dict:
    from qiskit import transpile
    backend, Sampler = local_sampler()
    qc = transpile(build_circuit(Q, p), backend, optimization_level=1)
    sampler = Sampler(options={"backend_options": {"method": "statevector"},
                               "run_options": {"seed_simulator": seed}})
    res = sampler.run([(qc, params)], shots=shots).result()[0]
    return res.data.meas.get_counts()


def cvar(Q: np.ndarray, counts: dict, alpha: float = 0.25) -> float:
    X, c = counts_to_arrays(counts)
    E = energies(Q, X)
    order = np.argsort(E)
    keep, acc, s = alpha * c.sum(), 0.0, 0.0
    for i in order:
        take = min(c[i], keep - acc)
        s += E[i] * take
        acc += take
        if acc >= keep:
            break
    return s / keep


@lru_cache(maxsize=64)
def _device_stats_cached(key: bytes, m: int, p: int) -> dict:
    """Depth / 2-qubit gate count after transpiling for a 156-qubit IBM Heron (fake backend)."""
    from qiskit import transpile
    from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
    Q = np.frombuffer(key, dtype=float).reshape(m, m)
    qc = build_circuit(Q, p)
    # non-zero angles: with zeros the transpiler would delete every rotation
    qc = qc.assign_parameters(np.full(qc.num_parameters, 0.37))
    t = transpile(qc, FakeMarrakesh(), optimization_level=3, seed_transpiler=7)
    ops = t.count_ops()
    two_q = int(sum(v for k, v in ops.items() if k in ("cz", "ecr", "cx", "rzz")))
    return {"qubits": m, "layers": p, "device": "FakeMarrakesh (IBM Heron r2, 156q)",
            "depth": int(t.depth()), "two_qubit_gates": two_q,
            "two_qubit_depth": int(t.depth(lambda ins: ins.operation.num_qubits == 2))}


def device_stats(Q: np.ndarray, p: int) -> dict:
    Qc = np.ascontiguousarray(Q, dtype=float)
    return dict(_device_stats_cached(Qc.tobytes(), len(Qc), p))


def solve_qaoa(inst: Instance, p: int = 3, shots: int = 2048, maxiter: int = 80,
               alpha: float = 0.5, seed: int = 0, with_device_stats: bool = True,
               init_delta: float = 1.0, **_) -> SolveResult:
    t0 = time.perf_counter()
    Q = inst.Q
    history = []

    def objective(th):
        v = cvar(Q, run_local(Q, p, th, shots=shots, seed=seed), alpha)
        history.append(v)
        return v

    # start from a linear-ramp (annealing-like) schedule, then let the optimizer reshape it
    res = minimize(objective, lr_params(p, init_delta), method="COBYLA", options={"maxiter": maxiter, "rhobeg": 0.2})
    counts = run_local(Q, p, res.x, shots=shots, seed=seed + 1)
    X, c = counts_to_arrays(counts)
    stats = device_stats(Q, p) if with_device_stats else None
    return summarise_samples(
        inst, X, c, "qaoa", time.perf_counter() - t0, circuit=stats,
        provenance={"backend": "qiskit-aer statevector (local)", "layers": p, "shots": shots,
                    "optimizer": "COBYLA", "init": f"linear ramp delta={init_delta}", "objective": f"CVaR alpha={alpha}", "evaluations": len(history),
                    "params": [round(float(v), 5) for v in res.x], "seed": seed,
                    "cvar_history": [round(float(v), 4) for v in history]},
    )


def tune_anneal(Q: np.ndarray, ps=(3, 5, 8), deltas=(0.4, 0.7, 1.0, 1.3), shots: int = 1024, seed: int = 0):
    """Grid over the schedule (p, Δ) on the simulator; pick the best mean energy."""
    best = None
    for p in ps:
        for d in deltas:
            X, c = counts_to_arrays(run_local(Q, p, lr_params(p, d), shots=shots, seed=seed))
            mean_e = float((energies(Q, X) * c).sum() / c.sum())
            if best is None or mean_e < best[0]:
                best = (mean_e, p, d)
    return best[1], best[2]


def solve_danneal(inst: Instance, p: int | None = None, delta: float | None = None, shots: int = 2048,
                  seed: int = 0, with_device_stats: bool = True, **_) -> SolveResult:
    t0 = time.perf_counter()
    Q = inst.Q
    tuned = p is None or delta is None
    if tuned:
        p, delta = tune_anneal(Q, seed=seed)
    params = lr_params(p, delta)
    counts = run_local(Q, p, params, shots=shots, seed=seed + 1)
    X, c = counts_to_arrays(counts)
    stats = device_stats(Q, p) if with_device_stats else None
    return summarise_samples(
        inst, X, c, "danneal", time.perf_counter() - t0, circuit=stats,
        provenance={"backend": "qiskit-aer statevector (local)", "schedule": "linear ramp (LR-QAOA)",
                    "layers": p, "delta": delta, "schedule_tuned_on_simulator": tuned, "shots": shots,
                    "params": [round(float(v), 5) for v in params], "seed": seed},
    )
