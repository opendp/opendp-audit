"""Probe outer Context.contingency_table with a public prior MBI table.

Model and estimator are fully public; private data influence only OpenDP's
certified frame transformations and private selection/noise. Uses the explicitly
enabled honest-but-curious API for table reuse and deterministic public fitting.
"""
import numpy as np
import jax
jax.config.update("jax_enable_x64", True)
import polars as pl
import mbi
import opendp.prelude as dp
from opendp.extras.mbi import ContingencyTable, Marginals, AIM, MST, Count

TOTAL = float(2**55 + 16)


def make_public_table():
    mbi_domain = mbi.Domain.fromdict({"A": 3, "B": 3, "C": 3})
    logs = np.full(mbi_domain.shape, -1000.0, dtype=np.float64)
    logs[0, 0, 0] = 0.0
    potentials = mbi.CliqueVector(
        mbi_domain, [("A", "B", "C")],
        {("A", "B", "C"): mbi.Factor(mbi_domain, logs)},
    )
    model = mbi.MarkovRandomField(
        potentials=potentials,
        marginals=mbi.CliqueVector(mbi_domain, [], {}),
        total=TOTAL,
    )
    # Include the latent null bucket expected in the high-level table.
    keys = {
        c: pl.Series(c, [0, 1, None], dtype=pl.UInt32)
        for c in ("A", "B", "C")
    }
    return ContingencyTable(keys=keys, cuts={}, marginals=Marginals(), model=model)


def neighbor(add_record=False):
    values = {"A": [0] * 4, "B": [0] * 4, "C": [0] * 4}
    if add_record:
        for col, x in (("A", 0), ("B", 1), ("C", 0)):
            values[col].append(x)
    return pl.LazyFrame({
        col: pl.Series(col, x, dtype=pl.UInt32) for col, x in values.items()
    })


def verify_context_selection_privacy_gap(table, algorithm_type):
    """Compute exact source selection event probabilities on 3-bin marginals."""
    from itertools import permutations
    from math import exp, log
    from opendp.extras.mbi._utilities import typed_dict_domain, typed_dict_distance
    from opendp.extras.mbi._mst import _make_mst_scores
    from opendp.extras.mbi._aim import _make_aim_scores
    from opendp.mod import binary_search

    model = table.model
    cliques = (
        (("A", "B"), ("A", "C"), ("B", "C"))
        if algorithm_type == "MST" else (("A",), ("B",))
    )
    domain = typed_dict_domain({
        clique: dp.numpy.arrayd_domain(shape=(3,) * len(clique), T="i32")
        for clique in cliques
    })
    metric = typed_dict_distance(
        dp.l01inf_distance(dp.absolute_distance(T="i32"))
    )
    d_in = {clique: (1, 1, 1) for clique in cliques}

    # Build exactly the indexed marginals produced by one 010 insertion.
    before, after = {}, {}
    inserted = {"A": 0, "B": 1, "C": 0}
    for clique in cliques:
        first = np.zeros((3,) * len(clique), dtype=np.int32)
        first[(0,) * len(clique)] = 4
        second = first.copy()
        second[tuple(inserted[c] for c in clique)] += 1
        before[clique], after[clique] = first, second

    if algorithm_type == "MST":
        scorer = _make_mst_scores(domain, metric, cliques, model)
    else:
        # d_measure=0.5, marginal L1=1, pure-DP scale=2 per cell.
        # Thus each public expectation is 2 and the full penalty is 6.
        scorer = _make_aim_scores(
            domain, metric, [Count(c) for c in cliques],
            {c: 2.0 for c in cliques}, model,
        )

    scores0 = np.asarray(scorer(before), dtype=np.float64)
    scores1 = np.asarray(scorer(after), dtype=np.float64)
    bound = scorer.map(d_in)
    assert bound == 1.0
    print("Context", algorithm_type, "scores before", scores0.tolist(),
          "after", scores1.tolist(), "delta", (scores1 - scores0).tolist(),
          "claimed sensitivity", bound, flush=True)

    # As in _make_aim_marginal and MST.make_marginals: first-round budget
    # split 50/50, twice rounded down before private selection.
    d_select = float(np.nextafter(np.nextafter(0.5, -np.inf), -np.inf))
    scale = binary_search(
        lambda x: x > 0 and (
            scorer >> dp.m.then_noisy_max(
                output_measure=dp.max_divergence(), scale=x
            )
        ).check(d_in, d_select),
        bounds=(0.0, None),
        T=float,
    )

    def selection_probability(scores, idx):
        maximum = max(scores)
        probs = [exp((float(v) - maximum) / scale) for v in scores]
        count, total = 0.0, 0.0
        for order in permutations(range(len(scores))):
            reaches = 1.0
            for candidate in order:
                if candidate == idx:
                    count += reaches * probs[idx]
                    break
                reaches *= 1.0 - probs[candidate]
            total += 1.0
        return count / total

    # Pick the score that is strictly lower only on the second dataset;
    # it is exposed by Marginals.cliques() in the Context release.
    differences = scores1 - scores0
    selected_index = int(np.argmin(differences))
    p0 = selection_probability(scores0, selected_index)
    p1 = selection_probability(scores1, selected_index)
    log_ratio = log(p0 / p1)
    print("Context", algorithm_type, "selection scale", scale,
          "exposed event", cliques[selected_index],
          "probabilities", p0, p1, "log ratio", log_ratio,
          "overall claimed epsilon", 1.0, flush=True)
    assert log_ratio > 1.0
    return log_ratio


def run_algorithm(algorithm_type):
    table = make_public_table()
    verify_context_selection_privacy_gap(table, algorithm_type)

    def keep_public_model(domain, marginals, *, potentials=None):
        assert domain.config == table.model.domain.config
        return table.model

    for added in (False, True):
        data = neighbor(added)
        context = dp.Context.compositor(
            data=data,
            privacy_unit=dp.unit_of(contributions=1),
            privacy_loss=dp.loss_of(epsilon=1.0),
        )
        algo = (
            MST(estimator=keep_public_model, num_selections=1, measure_split=0.5,
                oneway_split=0)
            if algorithm_type == "MST"
            else AIM(estimator=keep_public_model, queries=[Count(("A",)),Count(("B",))],
                     rounds=1, measure_split=0.5, oneway_split=0)
        )
        release = (
            context.query(epsilon=1.0)
            .select("A", "B", "C")
            .contingency_table(table=table, algorithm=algo)
            .release()
        )
        assert isinstance(release, ContingencyTable)
        cliques = release.marginals.cliques()
        print("Context", algorithm_type, "added", added,
              "cliques", cliques,
              "total model", release.model.total,
              flush=True)
        assert len(cliques) == 1, cliques
        if algorithm_type == "MST":
            assert tuple(cliques[0]) in (
                ("A", "B"), ("A", "C"), ("B", "C")
            )
        else:
            assert tuple(cliques[0]) in (("A",), ("B",))


def main():
    dp.enable_features("contrib", "idealized-numerics", "honest-but-curious")
    run_algorithm("MST")
    run_algorithm("AIM")


if __name__ == "__main__":
    main()
