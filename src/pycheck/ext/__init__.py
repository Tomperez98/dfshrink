"""Per-library adapters that turn validators into failure predicates.

``pycheck`` core knows nothing about validators: :func:`pycheck.shrink_rows`
takes a plain ``DataFrame -> bool`` predicate.  Each module here owns the
adapter for one real library, so importing the module is what pulls in that
library -- the base ``pycheck`` package never does.

* :mod:`pycheck.ext.dataframely` -- ``is_valid(df) -> bool`` schemas.
* :mod:`pycheck.ext.pandera` -- ``validate(df)``-raises schemas.
* :mod:`pycheck.ext.patito` -- ``Model.validate(df)``-raises models.

Use them as::

    from pycheck.ext.dataframely import shrink_rows
    repro = shrink_rows(df, HouseSchema)

Each module also exposes :func:`as_predicate` if you want the raw predicate.
"""
