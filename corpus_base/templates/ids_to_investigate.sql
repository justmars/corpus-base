WITH justice_data AS (
    SELECT
        start_term,
        inactive_date
    FROM
        sc_justices_tbl
    WHERE
        (
            dtl.raw_ponente = alias
            OR dtl.raw_ponente = LOWER(last_name)
        )
)
SELECT
    dtl.raw_ponente,
    (
        SELECT
            start_term
        FROM
            justice_data
    ) start_date,
    (
        SELECT
            inactive_date
        FROM
            justice_data
    ) end_date,
    MIN(
        dtl.date
    ),
    MAX(
        dtl.date
    ),
    COUNT(*) num
FROM
    sc_decisions_tbl dtl
WHERE
    justice_id IS NULL
    AND per_curiam IS 0
    AND raw_ponente IS NOT NULL
GROUP BY
    raw_ponente
ORDER BY
    num DESC
