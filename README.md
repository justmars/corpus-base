# Corpus Base

Validator of inputs from raw files for the following sqlite db tables:

1. Justices
2. Decisions
3. Citations
4. Votelines
5. Titletags

## Setup

### Database File

`DB_FILE` .env will be used as the path to create the database, e.g.

```zsh
DB_FILE="target_dir/sc.db"  # will create the database file at Path().home() / target_dir / sc.db
```

### Decision Files

`DecisionSourceFiles` will be used as path to source decision files, e.g.

```zsh
DecisionSourceFiles="corpus"
```

See staging directory:

```python
Path().home().joinpath("corpus").glob("**/*/details.yaml")
```

### Repo Tokens

- `OWNER`,
- `REPOSITORY` (of source files),
- `EXPIRING_TOKEN` (see Github PAT generation).

The source of justice information is the `sc.yaml` file stored in the Github Repository. We can make a more detailed copy of this file, supplying mandatory `retire` and `inactive` dates, through the following invocation:

```python
>>> from corpus_cite import Justice
>>> Justice.from_api()
PosixPath('path_to_repo/sc.yaml')
```

### Settings

```python
>>>from corpus_cite.settings import settings
>>>settings
BaseCaseSettings(
    DecisionSourceFiles='code/corpus/decisions',
    DatabasePath='code/corpus-cite/sc.db',
    GithubOwner='justmars',
    GithubRepo='corpus',
    JusticeTableName='justice_tbl',
    DecisionTableName='decisions_tbl',
    CitationTableName='decision_citations_tbl',
    VotelineTableName='decision_votelines_tbl',
    TitleTagTableName='decision_titletags_tbl'
)
```

### Initialize

```python
>>>from corpus_cite import init
>>>init()
```

## Features

### Insert records

Can add all pydantic validated records from the local copy of justices to the database.

```python
>>> from corpus_cite import Justice
>>> from corpus_cite.settings import settings as x

>>> Justice.init_justices_tbl(x)
<Database <sqlite3.Connection object at 0x10b7c8540>>

>>> x.db[x.JusticeTableName]
<Table justice_tbl (id, first_name, last_name, full_name, suffix, alias, gender, birth_date, start_term, end_term, chief_date, retire_date, inactive_date)>
```

### Clean raw ponente string

Each `ponente` name stored in `decisions_tbl` of the database has been made uniform, e.g.:

```python
>>> from corpus_vote import RawPonente
>>> RawPonente.clean("REYES , J.B.L, Acting C.J.") # sample name 1
"reyes, j.b.l."
>>> RawPonente.clean("REYES, J, B. L. J.") # sample name 2
"reyes, j.b.l."
```

We can see  most common names in the `ponente` field and the covered dates, e.g. from 1954 to 1972 (dates found in the decisions), there have been 1053 decisions marked with `jbl` (as cleaned):

```python
>>> from corpus_cite.helpers import most_popular
>>> [i for i in most_popular(db)] # excluding per curiams and unidentified cases
[
    ('1994-07-04', '2017-08-09', 'mendoza', 1297),
    ('1921-10-22', '1992-07-03', 'paras', 1287),
    ('2009-03-17', '2021-03-24', 'peralta', 1243),
    ('1998-06-18', '2009-10-30', 'quisumbing', 1187),
    ('1999-06-28', '2011-06-02', 'ynares-santiago', 1184),
    ('1956-04-28', '2008-04-04', 'panganiban', 1102),
    ('1936-11-19', '2009-11-05', 'concepcion', 1058),
    ('1954-07-30', '1972-08-18', 'reyes, j.b.l.', 1053),
    ('1903-11-21', '1932-03-31', 'johnson', 1043),
    ('1950-11-16', '1999-05-23', 'bautista angelo', 1028),
    ('2001-11-20', '2019-10-15', 'carpio', 1011),
    ...
]
```

This is retrieved through the following sql query:

```sql
select min(date), max(date), raw_ponente, count(*) num
from decisions_tbl
where raw_ponente is not null
group by raw_ponente
order by num desc
```

### Isolate active justices on date

When selecting a ponente or voting members, create a candidate list of justices based on date:

```python
>>> from corpus_vote import Justice
>>> Justice.get_active_on_date('Dec. 1, 1995') # target date
[
    {
        'id': 137,
        'surname': 'panganiban',
        'alias': None,
        'start_term': '1995-10-05', # since start date is greater than target date, record is included
        'inactive_date': '2006-12-06',
        'chief_date': '2005-12-20'
    },
    {
        'id': 136,
        'surname': 'hermosisima',
        'alias': 'hermosisima jr.',
        'start_term': '1995-01-10',
        'inactive_date': '1997-10-18',
        'chief_date': None
    },
]
```

### Designation as chief or associate

Since we already have candidates, we can cleaning desired option to get the `id` and `designation`:

```python
>>> from corpus_cite import RawPonente
>>> RawPonente.clean('Panganiban, Acting Cj')
'panganiban'
>>> Justice.get_justice_on_date('2005-09-08', 'panganiban')
{
    'id': 137,
    'surname': 'Panganiban',
    'start_term': '1995-10-05',
    'inactive_date': '2006-12-06',
    'chief_date': '2005-12-20',
    'designation': 'J.' # note variance
}
```

Note that the raw information above contains 'Acting Cj' and thus the designation is only 'J.'

At present we only track 'C.J.' and 'J.' titles.

With a different date, we can get the 'C.J.' designation.:

```python
>>> Justice.get_justice_on_date('2006-03-30', 'panganiban')
{
    'id': 137,
    'surname': 'Panganiban',
    'start_term': '1995-10-05',
    'inactive_date': '2006-12-06',
    'chief_date': '2005-12-20',
    'designation': 'C.J.' # corrected
}
```

### View chief justice dates

```python
>>> from corpus_vote import Justice
>>> Justice.view_chiefs()
[
    {
        'id': 178,
        'last_name': 'Gesmundo',
        'chief_date': '2021-04-05',
        'max_end_chief_date': None,
        'actual_inactive_as_chief': None,
        'years_as_chief': None
    },
    {
        'id': 162,
        'last_name': 'Peralta',
        'chief_date': '2019-10-23',
        'max_end_chief_date': '2021-04-04',
        'actual_inactive_as_chief': '2021-03-27',
        'years_as_chief': 2
    },
    {
        'id': 163,
        'last_name': 'Bersamin',
        'chief_date': '2018-11-26',
        'max_end_chief_date': '2019-10-22',
        'actual_inactive_as_chief': '2019-10-18',
        'years_as_chief': 1
    },
    {
        'id': 160,
        'last_name': 'Leonardo-De Castro',
        'chief_date': '2018-08-28',
        'max_end_chief_date': '2018-11-25',
        'actual_inactive_as_chief': '2018-10-08',
        'years_as_chief': 0
    }...
]
```
