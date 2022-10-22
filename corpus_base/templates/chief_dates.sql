WITH end_chief_date(d) AS (
    -- For each chief justice, get a second date: the date that the next chief justice is appointed; Can get this by getting the first chief date greater than the present chief date and using an ascending order. */
    SELECT
        DATE(
            tbl2.chief_date,
            '-1 day'
        )
    FROM
        {{ justice_table }}
        tbl2
    WHERE
        tbl2.chief_date IS NOT NULL
        AND tbl2.chief_date > tbl1.chief_date
    ORDER BY
        tbl2.chief_date ASC
    LIMIT
        1
), time_as_chief(period) AS (
    -- Difference between the two chief dates: that will be the time served as chief in years format */
    SELECT
        (
            SELECT
                DATE(d)
            FROM
                end_chief_date
        ) - DATE(
            tbl1.chief_date
        )
)
SELECT
    tbl1.id,
    tbl1.last_name,
    tbl1.chief_date,
    (
        SELECT
            d
        FROM
            end_chief_date
    ) max_end_chief_date,
    MIN(
        tbl1.inactive_date,
        (
            SELECT
                d
            FROM
                end_chief_date
        )
    ) actual_inactive_as_chief,
    (
        SELECT
            period
        FROM
            time_as_chief
    ) years_as_chief
FROM
    {{ justice_table }}
    tbl1
WHERE
    tbl1.chief_date IS NOT NULL
ORDER BY
    tbl1.chief_date DESC
