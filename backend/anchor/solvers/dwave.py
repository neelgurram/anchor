"""Real quantum annealer: D-Wave Advantage via Leap (dwave-system).

Only called from scripts/run_hardware.py, after Neel's explicit go. The API token is read
at run time (typed in, or the DWAVE_API_TOKEN environment variable) and never written to
disk. The app replays the saved results with their problem IDs and QPU timing.
"""
from __future__ import annotations

import time

import numpy as np

from . import Instance, SolveResult, summarise_samples


def solve_dwave(inst: Instance, token: str, num_reads: int = 1000, solver: str | None = None,
                annealing_time: float | None = None, **_) -> SolveResult:
    import dimod
    from dwave.system import DWaveSampler, EmbeddingComposite

    m = inst.m
    Q = {(i, j): float(inst.Q[i, j]) for i in range(m) for j in range(i, m) if inst.Q[i, j] != 0}
    bqm = dimod.BinaryQuadraticModel.from_qubo(Q)
    qpu = DWaveSampler(token=token, **({"solver": solver} if solver else {}))
    sampler = EmbeddingComposite(qpu)
    kw = {"num_reads": num_reads, "label": f"anchor {inst.problem.case_id} m={m}",
          "return_embedding": True}
    if annealing_time:
        kw["annealing_time"] = annealing_time
    t0 = time.perf_counter()
    ss = sampler.sample(bqm, **kw)
    wall = time.perf_counter() - t0
    agg = ss.aggregate()
    X = np.array([[s.get(i, 0) for i in range(m)] for s in agg.samples()], dtype=bool)
    counts = np.asarray(agg.record.num_occurrences)
    timing = ss.info.get("timing", {})
    emb = ss.info.get("embedding_context", {}).get("embedding", {})
    chain_lengths = [len(v) for v in emb.values()] if emb else []
    return summarise_samples(
        inst, X, counts, "dwave", wall,
        qpu_time=timing.get("qpu_access_time", 0) / 1e6 if timing else None,
        circuit={"qubits_logical": m, "physical_qubits": int(sum(chain_lengths)),
                 "max_chain_length": int(max(chain_lengths)) if chain_lengths else None,
                 "device": qpu.solver.name},
        provenance={"backend": qpu.solver.name, "num_reads": num_reads,
                    "problem_id": ss.info.get("problem_id"), "timing_us": timing,
                    "annealing_time_us": annealing_time or "default"},
    )
