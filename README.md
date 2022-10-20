# Corpus Cite

Validator of inputs from raw files for the following sqlite db tables:

1. Decisions
2. Citations
3. Votelines
4. Titletags

## Clean raw ponente string

Each `ponente` name stored in `raw_votes_tbl` of the database is not clean, i.e. cannot match this name to the `justices_tbl` with confidence. Need to run the `clean_raw_ponente()` function to get uniform results:

```python
>>> from corpus_vote import clean_raw_ponente
>>> clean_raw_ponente("REYES , J.B.L, Acting C.J.") # sample name 1
"reyes, j.b.l."
>>> clean_raw_ponente("REYES, J, B. L. J.") # sample name 2
"reyes, j.b.l."
```

In the `decisions_tbl` of the database, we can see the most common names in the `ponente` field and the covered dates, e.g. from 1954 to 1972 (dates found in the decisions), there have been 1053 decisions marked with `jbl` (as cleaned):

```python
>>> from corpus_cite.utils import get_cleaned_names
>>> [i for i in get_cleaned_names(db)] # excluding per curiams and unidentified cases
[
    ('1994-07-04', '2017-08-09', 'mendoza', 1294), # combined: vv m. (1994); j.m. (2010)
    ('2009-03-17', '2021-03-24', 'peralta', 1242),
    ('1998-06-18', '2009-10-30', 'quisumbing', 1185),
    ('1999-06-28', '2011-06-02', 'ynares-santiago', 1182),
    ('1994-02-13', '2008-04-04', 'panganiban', 1096),
    ('1903-11-21', '1932-03-31', 'johnson', 1029),
    ('2001-11-20', '2019-10-15', 'carpio', 1008),
    ('2002-10-15', '2011-06-15', 'carpio-morales', 924),
    ('2004-09-13', '2009-12-04', 'chico-nazario', 908),
    ('2011-11-28', '2021-09-28', 'perlas-bernabe', 870),
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
