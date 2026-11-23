"""End-to-end MST/AIM algorithm API release using a public MBI model.

The public estimator is deterministic and ignores private inputs. Honest-but-curious
must be enabled for it. A successful returned marginal's clique exposes the private
selection result, which would be a deterministic observable event in the release.
This does not test the outer make_contingency_table or Context wrapper.
"""
import numpy as np
import jax
jax.config.update("jax_enable_x64", True)
import polars as pl
import mbi
import opendp.prelude as dp
from opendp.extras.mbi import AIM, MST, Count, Marginals


TOTAL = float(2**55 + 16)


def public_model():
    domain = mbi.Domain.fromdict({"A": 2, "B": 2, "C": 2})
    logs = np.full(domain.shape, -1000.0, dtype=np.float64)
    logs[0, 0, 0] = 0.0
    log_factors = mbi.CliqueVector(
        domain,
        [("A", "B", "C")],
        {("A", "B", "C"): mbi.Factor(domain, logs)},
    )
    return mbi.MarkovRandomField(
        potentials=log_factors,
        marginals=mbi.CliqueVector(domain, [], {}),
        total=TOTAL,
    )


def data_for_neighbor(with_addition):
    columns = {
        "A": [0] * 4,
        "B": [0] * 4,
        "C": [0] * 4,
    }
    if with_addition:
        for name, val in (("A", 0), ("B", 1), ("C", 0)):
            columns[name].append(val)
    return pl.LazyFrame({
        name: pl.Series(name, rows, dtype=pl.UInt32)
        for name, rows in columns.items()
    })


def release(algorithm, model, space, distance, name):
    m = algorithm.make_marginals(
        *space, dp.max_divergence(),
        d_in=distance, d_out=1.0,
        marginals=Marginals(), model=model,
    )
    eps = m.map(distance)
    print(name, "public algorithm epsilon", eps, flush=True)
    assert 0 < eps <= 1.0
    choices = set()
    for added in (False, True):
        value = data_for_neighbor(added)
        assert space[0].member(value)
        released_marginals, released_model = m(value)
        cliques = released_marginals.cliques()
        print(name, "neighbor", added, "released cliques", cliques, flush=True)
        assert len(cliques) == 1, ("release does not expose one selection", cliques)
        assert isinstance(released_model, mbi.MarkovRandomField)
        choices.add(tuple(cliques[0]))
    return choices


def main():
    dp.enable_features("contrib", "idealized-numerics", "honest-but-curious")
    model = public_model()
    domain = dp.lazyframe_domain([
        dp.series_domain(col, dp.atom_domain(T="u32", bounds=(0, 1)))
        for col in ("A", "B", "C")
    ])
    space = domain, dp.frame_distance(dp.symmetric_distance())
    distance = [dp.polars.Bound(per_group=1)]

    # Public deterministic postprocessor: no private-data-dependent callbacks.
    def keep_public_model(domain, marginals, *, potentials=None):
        return model

    release(
        MST(estimator=keep_public_model, num_selections=1, measure_split=0.5),
        model, space, distance, "MST",
    )
    release(
        AIM(
            estimator=keep_public_model,
            queries=[Count(("A",)), Count(("B",))],
            rounds=1, measure_split=0.5,
        ),
        model, space, distance, "AIM",
    )


if __name__ == "__main__":
    main()
