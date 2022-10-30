# Corpus-Base

Builds on top of *corpus-persons* to create additional tables related to the Supreme Court:

## Setup .env

```zsh
CF_ACCT=XXX # account for cloudflare images
CF_TOKEN=XXX # token to access cloudflare images
EXPIRING_TOKEN=XXX # token to access github repository
DB_FILE=XXX # see sqlpyd
```

## Review database connection

Use the database path declared in DB_FILE to establish an sqlite3 connection:

```python
>>> from sqlpyd import Connection # this is sqlite-utils' Database() under the hood
>>> c = Connection() # type: ignore
Connection(DatabasePath='ex.db', WALMode=False) # the filename will later be created in the root directory of the project folder
```

The connection will be used for adding content to the database.

## Setup corpus-persons

Create and populate the *persons*-related tables:

```python
>>> from corpus_persons.__main__ import init_persons
>>> init_persons(c)
```

This creates tables associated with:

1. Individuals
2. Organizations

Individuals can be part of Organizations.

Individuals can be authors and formatters of corpus-originating works.

## Setup corpus-base

```python
>>> from corpus_base import build_sc_tables
>>> build_sc_tables(c)
```

This creates tables associated with:

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

Parse through a locally downloaded repository to populate the tables just created. Since there are thousands of cases, can limit the number of downloads via the `test_only` function attribute. The path location of the downloaded repository is [hard-coded](./corpus_base/utils/resources.py) since this package is intended to be run locally. Instructions for downloading and updating the repository are discussed elsewhere.
