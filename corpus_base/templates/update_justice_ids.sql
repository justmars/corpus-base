WITH candidate_justices AS (
    SELECT
        jt.id,
        jt.alias,
        jt.last_name,
        COUNT(*) num
    FROM
        {{ justice_tbl }}
        jt
    WHERE
        jt.inactive_date > d.date -- decision written before the justice became inactive
        AND d.date > jt.start_term -- decision written after the justice was appointed
        AND d.per_curiam != 1
        AND d.raw_ponente IS NOT NULL
        AND -- the decision raw ponente matches either:
        (
            d.raw_ponente = alias -- 1. the alias (already lower case); or
            OR d.raw_ponente = LOWER(
                jt.last_name
            ) -- 2.  the cleaned lower-cased last name of the justice
        )
    GROUP BY
        jt.id
    HAVING
        num = 1 -- ensure that only one justice id matches the criteria
),
justices_matched(
    decision_id,
    matched_justice_id
) AS (
    SELECT
        d.id,
        -- the decision id
        (
            SELECT
                id
            FROM
                candidate_justices
        ) -- the matched justice id
    FROM
        {{ decision_tbl }}
        d
)
UPDATE
    {{ decision_tbl }} AS dtbl -- update the decisions table with the newly matched justice id
    SET justice_id = m.matched_justice_id
FROM
    justices_matched m
WHERE
    dtbl.id = m.decision_id
