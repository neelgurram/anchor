"""API contract tests: shapes, units, live/replay flags, and that the numbers the UI shows
equal the backend's own evaluation."""
import base64
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from anchor import api

client = TestClient(api.app)
REQ = {"case_id": "Case12", "n_used": 6, "k": 2, "outlier_rate": 0.3, "seed": 9}


def f32(b64: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype=np.float32)


@pytest.fixture(scope="module")
def prob():
    r = client.post("/api/problem", json=REQ)
    assert r.status_code == 200
    return r.json()


def test_health_and_cases():
    assert client.get("/api/health").json() == {"ok": True, "cases": 22}
    cases = client.get("/api/cases").json()
    assert len(cases) == 22 and all(c["mean_shift_mm"] > 0 for c in cases)


def test_solver_list_flags_hardware_as_not_live():
    s = {x["id"]: x for x in client.get("/api/solvers").json()}
    assert s["exact"]["live"] and s["qaoa"]["live"]
    assert not s["ibm"]["live"] and not s["dwave"]["live"]


def test_brain_buffers_decode():
    b = client.get("/api/brain").json()
    assert f32(b["positions"]).size == 3 * b["n_vertices"]
    assert np.frombuffer(base64.b64decode(b["indices"]), np.uint32).size == 3 * b["n_faces"]


def test_problem_shapes(prob, ):
    m = prob["qubo"]["qubits"]
    assert m == REQ["n_used"] * REQ["k"] == len(prob["candidates"])
    assert len(prob["landmarks"]["mri_used"]) == REQ["n_used"]
    assert prob["metrics"]["n_held"] >= 3
    assert prob["metrics"]["tre_oracle"] < prob["metrics"]["tre_uncorrected"]
    n = client.get("/api/brain").json()["n_vertices"]
    assert f32(prob["true_shift"]["displacement"]).size == 3 * n
    w = f32(prob["true_shift"]["weight"])
    assert w.size == n and 0 <= w.min() and w.max() <= 1
    for a, b in prob["graph"]["edges"]:
        la, lb = prob["candidates"][a]["landmark"], prob["candidates"][b]["landmark"]
        assert la != lb                                    # one match per landmark, by construction


def test_unknown_case_404():
    assert client.post("/api/problem", json={**REQ, "case_id": "Case999"}).status_code == 404


@pytest.mark.parametrize("solver", ["naive", "exact", "ransac", "sa"])
def test_live_classical_solve(prob, solver):
    r = client.post("/api/solve", json={"problem_id": prob["problem_id"], "solver": solver, "params": {}})
    assert r.status_code == 200
    d = r.json()
    assert d["result"]["replay"] is False
    assert len(d["result"]["selection"]) == prob["qubo"]["qubits"]
    ev = d["evaluation"]
    assert ev["tre_uncorrected"] == pytest.approx(prob["metrics"]["tre_uncorrected"], abs=1e-3)
    assert ev["tre"] >= 0 and 0 <= ev["precision"] <= 1
    assert f32(d["error"]).size * 3 == f32(d["displacement"]).size


def test_exact_is_a_clique_with_ratio_one(prob):
    d = client.post("/api/solve", json={"problem_id": prob["problem_id"], "solver": "exact", "params": {}}).json()
    assert d["result"]["approx_ratio"] == pytest.approx(1.0)
    assert d["evaluation"]["tre"] < d["evaluation"]["tre_uncorrected"]


def test_live_qaoa_small(prob):
    d = client.post("/api/solve", json={"problem_id": prob["problem_id"], "solver": "qaoa",
                                        "params": {"p": 1, "shots": 256, "maxiter": 10,
                                                   "with_device_stats": False}}).json()
    assert d["result"]["replay"] is False and d["result"]["samples"]


def test_hardware_without_recording_is_404(prob, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "RESULTS", tmp_path)
    r = client.post("/api/solve", json={"problem_id": prob["problem_id"], "solver": "dwave", "params": {}})
    assert r.status_code == 404


def test_replay_rescored_from_raw_samples(prob, tmp_path, monkeypatch):
    """A recorded run is re-scored from its raw bitstrings; nothing precomputed is trusted."""
    monkeypatch.setattr(api, "RESULTS", tmp_path)
    m = prob["qubo"]["qubits"]
    truth = [int(c["true"]) for c in prob["candidates"]]
    run = {"solver": "dwave", "problem": REQ, "label": "test", "backend": "fake", "job_id": "job-1",
           "samples": {"bits": [truth, [0] * m], "counts": [7, 3]}, "qpu_time": 0.01, "wall_time": 1.0}
    (tmp_path / "hardware").mkdir()
    (tmp_path / "hardware" / "fake.json").write_text(json.dumps({"timestamp": "t", "runs": [run]}))
    d = client.post("/api/solve", json={"problem_id": prob["problem_id"], "solver": "dwave",
                                        "params": {"label": "test"}}).json()
    assert d["result"]["replay"] is True
    assert d["result"]["provenance"]["job_id"] == "job-1"
    assert d["evaluation"]["tre"] == pytest.approx(d["evaluation"]["tre_oracle"], abs=0.5)


def test_figure_name_is_sanitised():
    assert client.get("/api/figure/..%2Fsecret.png").status_code in (400, 404)
    assert client.get("/api/figure/missing.png").status_code == 404
