---
hide:
- navigation
- toc
---
# Misc

## Helper function to do things incrementally

```py
>>> from corpus_base import init_sc_cases
>>> init_sc_cases(c, test_only=10)
```

Since there are thousands of cases, can limit the number of downloads via the `test_only` function attribute.
