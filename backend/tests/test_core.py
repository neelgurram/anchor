import numpy as np
import pytest

from anchor.candidates import make_problem
from anchor.data import Case, list_cases, load_case, parse_tag
from anchor.graph import consistency_graph, is_clique, repair_to_clique
from anchor.qubo import brute_force, build_qubo, energy, max_weight_clique, to_ising
from anchor.registration import Warp, evaluate
from anchor.solvers import make_instance
from anchor.solvers.classical import solve_exact, solve_naive, solve_ransac, solve_sa
from anchor.solvers.quantum import bits_to_x

TAG = """MNI Tag Point File
Volumes = 2;
% test

Points =
 1.0 2.0 3.0 1.5 2.5 3.5 ""
 -4 5 6.25 -3 5 6 "";
"""


def test_parse_tag():
    a, b = parse_tag(TAG)
    assert a.shape == (2, 3) and b.shape == (2, 3)
    assert np.allclose(a[1], [-4, 5, 6.25]) and np.allclose(b[0], [1.5, 2.5, 3.5])


def test_resect_cases_present():
    ids = list_cases()
    assert len(ids) == 22
    c = load_case(ids[0])
    assert c.n >= 15 and c.mri.shape == c.us.shape


def random_graph(m, p, seed):
    rng = np.random.default_rng(seed)
    a = rng.random((m, m)) < p
    a = np.triu(a, 1)
    return a | a.T


@pytest.mark.parametrize("seed", range(8))
def test_qubo_optimum_equals_max_clique(seed):
    """Penalty validation: the QUBO minimum is exactly the maximum-weight clique."""
    m = 10 + seed
    adj = random_graph(m, 0.5, seed)
    w = 1 + 0.05 * np.random.default_rng(seed).random(m)
    Q = build_qubo(adj, w)
    xb, eb = brute_force(Q)
    xc, wc = max_weight_clique(adj, w)
    assert is_clique(adj, xb)
    assert np.isclose(eb, -wc)
    assert np.isclose(energy(Q, xc), -wc)


def test_repair_makes_clique():
    adj = random_graph(12, 0.4, 3)
    sel = np.ones(12, bool)
    w = np.ones(12)
    assert is_clique(adj, repair_to_clique(adj, sel, w))


def test_bits_endianness():
    # qubit 0 is the rightmost character
    assert list(bits_to_x("001")) == [True, False, False]


def test_ising_energy_matches_qubo():
    """x^T Q x must equal (scale * <z|H|z>) + offset for every basis state."""
    adj = random_graph(5, 0.5, 1)
    Q = build_qubo(adj, np.ones(5))
    H, offset, scale = to_ising(Q)
    import itertools
    for bits in itertools.product([0, 1], repeat=5):
        x = np.array(bits, float)
        z = 1 - 2 * x
        e = offset
        for pauli, c in zip(H.paulis, H.coeffs):
            idx = [i for i in range(5) if pauli.z[i]]
            e += scale * c.real * np.prod(z[idx])
        assert np.isclose(e, energy(Q, x))


def synthetic_case(n=15, seed=0):
    rng = np.random.default_rng(seed)
    mri = rng.uniform(-25, 25, (n, 3))
    us = mri + np.array([3.0, -2.0, 4.0])          # pure translation: TPS must be exact
    return Case("Synth", mri, us)


def test_tre_zero_for_exact_warp():
    c = synthetic_case()
    p = make_problem(c, n_used=10, k=1, outlier_rate=0.0, seed=0)
    p.cand_pos[:] = c.us[p.used_idx][p.cand_landmark]   # remove jitter
    ev = evaluate(c, p, np.ones(p.m, bool))
    assert ev.tre < 1e-6 and ev.tre_uncorrected > 5


def test_warp_kinds():
    src = np.random.default_rng(0).normal(size=(6, 3)) * 10
    assert Warp(src, src + 1).kind == "tps"
    assert Warp(src[:2], src[:2] + 1).kind == "translation"


@pytest.mark.parametrize("case_id", ["Case1", "Case12"])
def test_classical_solvers_on_real_case(case_id):
    c = load_case(case_id)
    p = make_problem(c, n_used=8, k=2, outlier_rate=0.3, seed=2)
    inst = make_instance(p)
    ex = solve_exact(inst)
    assert is_clique(inst.adj, ex.selection) and ex.approx_ratio == pytest.approx(1.0)
    sa = solve_sa(inst)
    assert is_clique(inst.adj, sa.selection)
    assert inst.w[sa.selection].sum() <= inst.opt_weight + 1e-9
    nv = solve_naive(inst)
    assert nv.selection.sum() == p.n_used
    rs = solve_ransac(inst)
    assert rs.selection.sum() >= 3


def test_consistency_beats_naive_on_average():
    """Benchmark sanity: with outliers, the exact clique gives lower held-out error than naive."""
    tre_ex, tre_nv = [], []
    for cid in list_cases()[:8]:
        c = load_case(cid)
        p = make_problem(c, n_used=8, k=2, outlier_rate=0.4, seed=0)
        inst = make_instance(p)
        tre_ex.append(evaluate(c, p, solve_exact(inst).selection).tre)
        tre_nv.append(evaluate(c, p, solve_naive(inst).selection).tre)
    assert np.mean(tre_ex) < np.mean(tre_nv)
