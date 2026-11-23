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


def run_algorithm(algorithm_type):
    table = make_public_table()

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
