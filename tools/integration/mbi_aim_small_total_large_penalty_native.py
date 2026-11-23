"""AIM high-level Context DP check with small public total and huge noise penalty.

This is a distinct parameter regime from large-public-model rounding: public
MBI total=2, with very small positive measure_split and selection budget ~1.
The estimator is public and deterministic under honest-but-curious.
"""
from itertools import permutations
from math import exp, log
import numpy as np
import jax
jax.config.update("jax_enable_x64", True)
import polars as pl
import mbi
import opendp.prelude as dp

from opendp.extras.mbi import AIM, ContingencyTable, Count, Marginals
from opendp.extras.mbi._aim import _make_aim_scores, _make_aim_select
from opendp.extras.mbi._utilities import typed_dict_domain, typed_dict_distance, make_noise_marginal

PENALTY = float(2**54 + 8)
NUM_CATEGORIES = 65  # pushes the penalty into a 4-ULP bin while noise scale stays < 2**49
MEASURE_SPLIT = NUM_CATEGORIES / PENALTY
CLIQUE_A = ("A",)
CLIQUE_B = ("B",)
CLIQUE_NAMES = (CLIQUE_A, CLIQUE_B)


def public_table():
    domain = mbi.Domain.fromdict({"A": NUM_CATEGORIES, "B": NUM_CATEGORIES, "C": NUM_CATEGORIES})
    logs = np.full(domain.shape, -1000.0, dtype=np.float64)
    logs[0, 0, 0] = 0.0
    logs[1, 0, 0] = 0.0
    potentials = mbi.CliqueVector(
        domain, [("A", "B", "C")],
        {("A", "B", "C"): mbi.Factor(domain, logs)},
    )
    model = mbi.MarkovRandomField(
        potentials=potentials,
        marginals=mbi.CliqueVector(domain, [], {}),
        total=2.0,
    )
    print("MBI small-model A:", model.project(CLIQUE_A).values, flush=True)
    print("MBI small-model B:", model.project(CLIQUE_B).values, flush=True)
    keys = {col: pl.Series(col, [*range(NUM_CATEGORIES - 1), None], dtype=pl.UInt32)
            for col in ("A", "B", "C")}
    return ContingencyTable(keys=keys, cuts={}, model=model, marginals=Marginals())


def marginal_tables(with_added):
    a = np.zeros(NUM_CATEGORIES, dtype=np.int32)
    b = np.zeros(NUM_CATEGORIES, dtype=np.int32)
    a[0] = b[0] = 2
    if with_added:
        a[0] += 1
        b[1] += 1
    return {CLIQUE_A: a, CLIQUE_B: b}


def probability(scores, index, scale):
    maximum = max(scores)
    accepts = [exp((float(v) - maximum) / scale) for v in scores]
    prob = 0.0
    for order in permutations(range(len(scores))):
        remaining = 1.0
        for i in order:
            if i == index:
                prob += remaining * accepts[i]
                break
            remaining *= 1 - accepts[i]
    return prob / 2  # two possible orders


def analytic_event_ratio(table):
    model = table.model
    d = typed_dict_domain({
        q: dp.numpy.arrayd_domain(shape=(NUM_CATEGORIES,), T="i32") for q in CLIQUE_NAMES
    })
    metric = typed_dict_distance(
        dp.l01inf_distance(dp.absolute_distance(T="i32"))
    )
    distance = {q: (1, 1, 1) for q in CLIQUE_NAMES}
    exact0, exact1 = marginal_tables(False), marginal_tables(True)
    assert d.member(exact0) and d.member(exact1)
    # Actual AIM formula is d_measure=measure_split*d_out, and with MaxDP
    # expected Laplace absolute noise = 1/d_measure per cell.
    d_measure = MEASURE_SPLIT
    expectations = {q: 1 / d_measure for q in CLIQUE_NAMES}
    score = _make_aim_scores(
        d, metric, [Count(q) for q in CLIQUE_NAMES], expectations, model
    )
    before = np.asarray(score(exact0), dtype=np.float64)
    after = np.asarray(score(exact1), dtype=np.float64)
    sensitivity = score.map(distance)
    print("AIM small public model scores", before, after,
          "delta", after - before,
          "penalty", NUM_CATEGORIES / d_measure,
          "sensitivity", sensitivity, flush=True)
    assert sensitivity == 1.0
    d_select = float(np.nextafter(np.nextafter(1.0 - d_measure, -np.inf), -np.inf))
    # Diagnose whether the second (count-noise) privacy search can meet the
    # unusually small measurement budget with finite valid noise scales.
    for trial_scale in (1e12, 1e14, 1e15, 1e16, 1e18, 1e100):
        try:
            m_noise = make_noise_marginal(
                d, metric, dp.max_divergence(),
                clique=CLIQUE_A, scale=trial_scale,
            )
            actual_eps = m_noise.map(distance)
            print("tiny-budget noise scale", trial_scale,
                  "epsilon", actual_eps,
                  "check", m_noise.check(distance, d_measure), flush=True)
        except Exception as err:
            print("tiny-budget noise scale", trial_scale, "ERROR",
                  type(err).__name__, str(err)[:500], flush=True)

    select = _make_aim_select(
        d, metric, dp.max_divergence(),
        d_in=distance, d_out=d_select, d_measure=d_measure,
        queries=[Count(q) for q in CLIQUE_NAMES],
        model=model, max_size=80.0,
    )
    assert select is not None
    selection_budget = select.map(distance)
    scale = dp.binary_search(
        lambda s: s > 0 and (
            score >> dp.m.then_noisy_max(
                output_measure=dp.max_divergence(), scale=s
            )
        ).check(distance, d_select),
        bounds=(0.0, None), T=float
    )
    idx = 1
    p0 = probability(before, idx, scale)
    p1 = probability(after, idx, scale)
    loss = log(p0 / p1)
    print("AIM small-model selection", "scale", scale,
          "budget", selection_budget,
          "event", CLIQUE_NAMES[idx],
          "P0", p0, "P1", p1,
          "log ratio", loss, flush=True)
    assert loss > 1.0
    return loss


def original_frame(with_added):
    rows = {
        "A": [0, 0],
        "B": [0, 0],
        "C": [0, 0],
    }
    if with_added:
        rows["A"].append(0)
        rows["B"].append(1)
        rows["C"].append(0)
    return pl.LazyFrame({
        col: pl.Series(col, vals, dtype=pl.UInt32)
        for col, vals in rows.items()
    })


def release_both(table):
    def public_estimator(domain, marginals, *, potentials=None):
        return table.model

    for added in (False, True):
        ctx = dp.Context.compositor(
            data=original_frame(added),
            privacy_unit=dp.unit_of(contributions=1),
            privacy_loss=dp.loss_of(epsilon=1.0),
        )
        algorithm = AIM(
            estimator=public_estimator,
            queries=[Count(CLIQUE_A), Count(CLIQUE_B)],
            rounds=1, measure_split=MEASURE_SPLIT, oneway_split=0,
        )
        result = (ctx.query(epsilon=1.0).select("A", "B", "C")
                  .contingency_table(table=table, algorithm=algorithm).release())
        assert isinstance(result, ContingencyTable)
        choices = result.marginals.cliques()
        print("AIM small-model Context added", added, "choice", choices, flush=True)
        assert len(choices) == 1 and choices[0] in CLIQUE_NAMES


if __name__ == "__main__":
    dp.enable_features("contrib", "idealized-numerics", "honest-but-curious")
    table = public_table()
    analytic_event_ratio(table)
    release_both(table)
