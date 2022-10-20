# Corpus Cite

Validator of inputs from raw files for the following sqlite db tables:

1. Decisions
2. Citations
3. Votelines
4. Titletags

## Clean raw ponente string

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
