import re

from markdownify import markdownify

VOTEFULL_MIN_LENGTH = 20
VOTELINE_MIN_LENGTH = 15
VOTELINE_MAX_LENGTH = 1000
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


def voteline_clean(text: str | None):
    if not text:
        return None
    text = text.lstrip(". ").rstrip()
    init = markdownify(text).replace("*", "").strip()
    if len(text) < VOTEFULL_MIN_LENGTH:
        return None
    clean = WHITELIST.sub("", init)
    add_concur_line = clean.replace("concur.", "concur.\n")
    unchair = CHAIRPERSON.sub("", add_concur_line)
    relined = multilines.sub("\n", unchair)
    startings = startlines.sub("", relined)
    endings = endlines.sub("", startings)
    return endings.strip()


def is_line_ok(text: str):
    has_proper_length = VOTELINE_MAX_LENGTH > len(text) > VOTELINE_MIN_LENGTH
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


def extract_votelines(decision_pk: str, text: str):
    for line in text.splitlines():
        if is_line_ok(line):
            yield dict(decision_id=decision_pk, text=line)
