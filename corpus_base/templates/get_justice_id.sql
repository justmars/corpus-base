SELECT
    jt.id,
    jt.alias,
    jt.last_name,
    jt.start_term,
    jt.inactive_date
FROM
    {{ justice_tbl }}
    jt
WHERE
    jt.inactive_date > '{{ target_date }}' -- decision written before the justice became inactive
    AND '{{ target_date }}' > jt.start_term -- decision written after the justice was appointed
    AND -- the decision raw ponente matches either:
    (
        '{{ target_name }}' = jt.alias -- 1. the alias (already lower case); or
        OR '{{ target_name }}' = LOWER(
            jt.last_name
        ) -- 2.  the cleaned lower-cased last name of the justice
    )
