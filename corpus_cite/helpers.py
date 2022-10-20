import re

from markdownify import markdownify
from sqlite_utils import Database

WHITELIST = re.compile(
    r""" # ^ exclusion [^ ... ]
    [^
        \w,
        \.
        ,
        \s
        \(
        \)
        \-
    ]+ # match all characters that are not included in the whitelist
    """,
    re.X,
)
CHAIRPERSON = re.compile(
    r"""
    [,\s;]*
    \(
        \s*
        (
            Acting|
            Working
        )?
        \s*
        Chair(
            man|
            person
        )
        \s*
    \)
    """,
    re.X | re.I,
)

multilines = re.compile(r"\s*\n+\s*")
startlines = re.compile(r"^[\.,\s]")
endlines = re.compile(r"\-+$")


def voteline_clean(text: str):
    init = markdownify(text).replace("*", "").strip()
    clean = WHITELIST.sub("", init)
    add_concur_line = clean.replace("concur.", "concur.\n")
    unchair = CHAIRPERSON.sub("", add_concur_line)
    relined = multilines.sub("\n", unchair)
    startings = startlines.sub("", relined)
    endings = endlines.sub("", startings)
    return endings.strip()


def is_line_ok(text: str):
    has_proper_length = 1000 > len(text) > 16
    has_indicator = re.search(r"(C\.|J\.)?J\.", text)
    not_all_caps = not text.isupper()
    first_char_capital_letter = re.search(r"^[A-Z]", text)
    return all(
        [
            has_proper_length,
            has_indicator,
            not_all_caps,
            first_char_capital_letter,
        ]
    )


## Database

db = Database("cases.db", use_counts_table=True)
