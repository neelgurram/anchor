"""Confidence engine: the hide-one check catches wrong matches, the alarm separates bad
maps from good ones, alternatives are valid, and the API ships a per-vertex spread map."""
import base64

import numpy as np
from fastapi.testclient import TestClient

from anchor import api, confidence as C
from anchor.candidates import make_problem
from anchor.data import load_case
from anchor.graph import is_clique
from anchor.solvers import make_instance
from anchor.solvers.registry import LIVE

client = TestClient(api.app)


def _demo():
    case = load_case("Case12")
    p = make_problem(case, n_used=8, k=2, outlier_rate=0.3, seed=9)
    return case, p, make_instance(p)


def test_true_matches_pass_the_hide_one_check():
    _, p, _ = _demo()
    idx, miss = C.hide_one(p, p.cand_true)
    assert len(idx) == p.n_used
    assert miss.mean() < C.ALARM_MM and not C.assess(p, p.cand_true).alarm


def test_one_wrong_match_is_the_worst_and_trips_the_alarm():
    _, p, _ = _demo()
    sel = p.cand_true.copy()
    lm = 0
    true_i = np.flatnonzero(p.cand_true & (p.cand_landmark == lm))[0]
    wrong_i = np.flatnonzero(~p.cand_true & (p.cand_landmark == lm))[0]
    sel[true_i], sel[wrong_i] = False, True               # swap in one decoy
    cf = C.assess(p, sel)
    assert cf.worst_index == wrong_i
    assert cf.worst_miss > 3 * np.median(cf.loo_miss)


def test_naive_alarms_exact_does_not():
    _, p, inst = _demo()
    assert C.assess(p, LIVE["naive"](inst).selection).alarm
    assert not C.assess(p, LIVE["exact"](inst).selection).alarm


def test_too_few_matches_alarms():
    _, p, _ = _demo()
    sel = p.cand_true.copy()
    sel[np.flatnonzero(sel)[:4]] = False
    cf = C.assess(p, sel)
    assert cf.alarm and any("trusted matches" in r for r in cf.reasons)


def test_alternatives_are_new_consistent_sets():
    _, p, inst = _demo()
    sel = inst.opt_x
    rng = np.random.default_rng(0)
    rows = rng.random((400, inst.m)) < 0.5
    from anchor.qubo import energies
    alts = C.alternatives(inst.adj, inst.w, sel, rows, energies(inst.Q, rows))
    assert len(alts) <= C.MAX_ALTERNATIVES
    keys = {tuple(a) for a in alts}
    assert len(keys) == len(alts) and tuple(sel) not in keys
    for a in alts:
        assert is_clique(inst.adj, a) and (a & ~sel).any()
        assert inst.w[a].sum() >= inst.w[sel].sum() - C.ALT_SLACK


def test_spread_is_zero_with_no_alternatives_to_compare():
    _, p, _ = _demo()
    pts = p.mri_used
    assert np.allclose(C.spread(p, p.cand_true, [], lambda w: w.displacement(pts)), 0)


def test_api_returns_confidence_and_spread_map():
    req = {"case_id": "Case12", "n_used": 8, "k": 2, "outlier_rate": 0.3, "seed": 9}
    pid = client.post("/api/problem", json=req).json()["problem_id"]
    n = client.get("/api/brain").json()["n_vertices"]
    out = {}
    for s in ("naive", "exact"):
        r = client.post("/api/solve", json={"problem_id": pid, "solver": s, "params": {}}).json()
        spread = np.frombuffer(base64.b64decode(r["spread"]), np.float32)
        assert spread.size == n and spread.min() >= 0
        out[s] = r["confidence"]
    assert out["naive"]["alarm"] and out["naive"]["reasons"]
    assert not out["exact"]["alarm"]
    assert out["exact"]["spread_median_mm"] < out["naive"]["spread_median_mm"]
