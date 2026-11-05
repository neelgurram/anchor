"""Name -> solver function, with display metadata used by the API and frontend."""
from __future__ import annotations

from .classical import solve_exact, solve_naive, solve_ransac, solve_sa
from .quantum import solve_danneal, solve_qaoa

LIVE = {
    "naive": solve_naive,
    "ransac": solve_ransac,
    "exact": solve_exact,
    "sa": solve_sa,
    "qaoa": solve_qaoa,
    "danneal": solve_danneal,
}

META = {
    "naive":   {"label": "Naive", "family": "baseline", "desc": "Trust each landmark's best-scoring match"},
    "ransac":  {"label": "RANSAC", "family": "classical", "desc": "Standard robust fit used in practice"},
    "exact":   {"label": "Exact", "family": "classical", "desc": "Exact maximum clique (the true optimum)"},
    "sa":      {"label": "Simulated annealing", "family": "classical", "desc": "Classical annealing on the same QUBO"},
    "qaoa":    {"label": "QAOA", "family": "gate", "desc": "Gate-based: tuned circuit, simulated on Aer"},
    "danneal": {"label": "Digitized anneal", "family": "gate-anneal", "desc": "Annealing schedule run as gates on Aer"},
    "ibm":     {"label": "IBM hardware", "family": "gate", "desc": "Recorded run on a real IBM Heron QPU"},
    "dwave":   {"label": "D-Wave annealer", "family": "anneal", "desc": "Recorded run on a real D-Wave QPU"},
}
