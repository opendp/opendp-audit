"""Native integration for AIM and MST numerical score sensitivity regressions.

Requires published OpenDP nightly, mbi==2.0.0, NumPy and JAX.
Construct a real MarkovRandomField with compatible public factor marginals,
execute actual OpenDP score transformations, then check composed privacy maps.
This is *internal* scorer-to-selection integration, not the full
make_contingency_table pipeline.
"""
import math
import numpy as np
import jax
jax.config.update("jax_enable_x64", True)
import mbi
import opendp.prelude as dp
from opendp.extras.mbi._utilities import (
    Count, typed_dict_domain, typed_dict_distance,
)
from opendp.extras.mbi._mst import _make_mst_scores
from opendp.extras.mbi._aim import _make_aim_scores


TOTAL = float(2**55 + 16)
EDGES = (("A", "B"), ("A", "C"), ("B", "C"))


def model_with_concentrated_public_joint():
    domain = mbi.Domain.fromdict({"A": 2, "B": 2, "C": 2})
    joint = np.zeros(domain.shape, dtype=np.float64)
    joint[0, 0, 0] = TOTAL
    # Construct an actual normalized model from finite log-potentials.
    # In binary64, exp(-1000) underflows to zero, so its projections are
    # exactly concentrated in the zero cell. Do NOT inject synthetic
    # marginals inconsistent with the model's potentials.
    log_potentials = np.full(domain.shape, -1000.0, dtype=np.float64)
    log_potentials[0, 0, 0] = 0.0
    potentials = mbi.CliqueVector(
        domain, [("A", "B", "C")],
        {("A", "B", "C"): mbi.Factor(domain, log_potentials)},
    )
    # Empty stored marginals forces MBI's real variable-elimination oracle.
    model = mbi.MarkovRandomField(
        potentials=potentials,
        marginals=mbi.CliqueVector(domain, [], {}),
        total=TOTAL,
    )
    assert isinstance(model, mbi.MarkovRandomField)
    for edge in EDGES:
        projected = np.asarray(model.project(edge).values)
        print("MBI variable-elimination projection", edge, repr(projected), flush=True)
        np.testing.assert_allclose(
            projected, [[TOTAL, 0.0], [0.0, 0.0]], rtol=1e-12, atol=0.0
        )
    for cl in (("A",), ("B",), ("C",)):
        projected = np.asarray(model.project(cl).values)
        np.testing.assert_allclose(
            projected, [TOTAL, 0.0], rtol=1e-12, atol=0.0
        )
    return model


def input_space(cliques):
    d = typed_dict_domain({
        clique: dp.numpy.arrayd_domain(shape=(2,) * len(clique), T="i32")
        for clique in cliques
    })
    m = typed_dict_distance(
        dp.l01inf_distance(dp.absolute_distance(T="i32"))
    )
    return d, m


def sample_mst():
    model = model_with_concentrated_public_joint()
    dom, metric = input_space(EDGES)
    before = {e: np.array([[4, 0], [0, 0]], dtype=np.int32) for e in EDGES}
    after = {
        ("A", "B"): np.array([[5, 0], [0, 0]], dtype=np.int32),
        ("A", "C"): np.array([[4, 1], [0, 0]], dtype=np.int32),
        ("B", "C"): np.array([[4, 1], [0, 0]], dtype=np.int32),
    }
    d_in = {e: (1, 1, 1) for e in EDGES}
    for name, value in (("before", before), ("after", after)):
        assert dom.member(value), ("mst domain member", name)
    t = _make_mst_scores(dom, metric, EDGES, model)
    a = np.asarray(t(before))
    b = np.asarray(t(after))
    print("MST scores:", a.tolist(), b.tolist(), "delta", (b - a).tolist(), flush=True)
    np.testing.assert_array_equal(b - a, [-8, 0, 0])
    bounded = t.map(d_in)
    print("MST native stability bound", bounded, flush=True)
    assert bounded == 1.0
    m = t >> dp.m.then_noisy_max(output_measure=dp.max_divergence(), scale=4.0)
    eps = m.map(d_in)
    print("MST native selection epsilon", eps, flush=True)
    assert 0 < eps <= 0.5
    # From exact permute-and-flip probabilities of these real score vectors:
    log_ratio = math.log((1.0 / 3) / (math.exp(-2) / 3))
    assert log_ratio > eps
    return log_ratio, eps


def sample_aim():
    model = model_with_concentrated_public_joint()
    cliques = (("A",), ("B",))
    dom, metric = input_space(cliques)
    before = {e: np.array([4, 0], dtype=np.int32) for e in cliques}
    after = {
        ("A",): np.array([5, 0], dtype=np.int32),
        ("B",): np.array([4, 1], dtype=np.int32),
    }
    d_in = {e: (1, 1, 1) for e in cliques}
    for name, value in (("before", before), ("after", after)):
        assert dom.member(value), ("aim domain member", name)
    t = _make_aim_scores(
        dom, metric, [Count(("A",)), Count(("B",))],
        {("A",): 2.0, ("B",): 2.0}, model,
    )
    a = np.asarray(t(before))
    b = np.asarray(t(after))
    print("AIM scores:", a.tolist(), b.tolist(), "delta", (b - a).tolist(), flush=True)
    np.testing.assert_array_equal(b - a, [-16, 0])
    bounded = t.map(d_in)
    print("AIM native stability bound", bounded, flush=True)
    assert bounded == 1.0
    m = t >> dp.m.then_noisy_max(output_measure=dp.max_divergence(), scale=4.0)
    eps = m.map(d_in)
    print("AIM native selection epsilon", eps, flush=True)
    assert 0 < eps <= 0.5
    # Two initially tied candidates, one lower by 16 after insertion.
    log_ratio = math.log((0.5) / (0.5 * math.exp(-4)))
    assert log_ratio > eps
    return log_ratio, eps


if __name__ == "__main__":
    print("OpenDP", getattr(dp, "__version__", "unknown"),
          "NumPy", np.__version__, "MBI", getattr(mbi, "__version__", "unknown"),
          "JAX x64", jax.config.jax_enable_x64, flush=True)
    dp.enable_features("contrib", "idealized-numerics")
    print("MST ratio / epsilon:", sample_mst(), flush=True)
    print("AIM ratio / epsilon:", sample_aim(), flush=True)
