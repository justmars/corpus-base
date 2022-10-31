# Corpus-Base

Builds on top of *corpus-persons* to create additional tables related to the Supreme Court.

```python
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

```python
>>> from corpus_base import init_sc_cases
>>> init_sc_cases(c, test_only=10)
```

Parse through a locally downloaded repository to populate tables. Since there are thousands of cases, can limit the number of downloads via the `test_only` function attribute. The path location of the downloaded repository is [hard-coded](./corpus_base/utils/resources.py) since this package is intended to be run locally. Instructions for downloading and updating the repository are discussed elsewhere.
