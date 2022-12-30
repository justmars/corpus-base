# Corpus-Base

Builds on top of *corpus-pax* to create additional tables related to the Supreme Court.

```python shell
>>> from corpus_base import build_sc_tables
>>> build_sc_tables(c)
```

This creates additional tables associated with:

1. Justices
2. Decisions
   - Citations
   - Votelines
   - Titletags
   - Opinions

```python shell
>>> from corpus_base import init_sc_cases
>>> init_sc_cases(c, test_only=10)
```

Parse through a locally downloaded repository to populate tables. Since there are thousands of cases, can limit the number of downloads via the `test_only` function attribute. The path location of the downloaded repository is [hard-coded](./corpus_base/utils/resources.py) since this package is intended to be run locally. Instructions for downloading and updating the repository are discussed elsewhere.

## Full steps

```python
from corpus_pax import init_persons, init_person_tables
from corpus_base import build_sc_tables, setup_case, init_sc_cases
from sqlpyd import Connection

c = Connection(DatabasePath="test.db")  # type: ignore
init_persons(c)  # for authors
build_sc_tables(c)
init_sc_cases(c, test_only=10)
```
