import re

XXX = re.compile(r"x\s*x\s*x\s*", re.I)
"""x x x"""

MIN_LENGTH_CHARS_IN_LINE = 500
"""The most important factor in determininig the number of segments to be added to the database"""

START_NOT_ALPHANUM = re.compile(r"^\W+")
"""Start of line is not alphanumeric"""

END_NOT_ALPHANUM = re.compile(r"\W+$")
"""End of line is not alphanumeric"""

FOOTNOTES = re.compile(r"\[\^\d+\]")
"""e.g. [^1]"""

STARTS_WITH_FOOTNOTE = re.compile(r"^\[\^\d+\]:")
"""In markdown footnotes, this is the start of the line `[^1]:`"""

EXTRA_SPACE = re.compile(r"\s+")
"""e.g. Multiple spaces"""

NO_LOWERCASE = re.compile(r"^[^a-z]*$")
"""Check if all uppercase"""

MIN_LENGTH_ALL_UPPER = 40
"""Combined with uppercase checker, must be less than 30 characters"""

STARTS_WITH_FOOTNOTE = re.compile(r"^\[\^\d+\]:")

FOOTNOTE_FILLER = re.compile(
    r"""
    ^(
        records,\s*p
        |tsn,
        |(ca\s*\*)?rollo
        |id
    )
    \W+ # non-alphanumeric, e.g. , .
    (.*?)
    \d$ # ends with a digit
    """,
    re.I | re.X,
)


def clean_segment(text: str):
    text = XXX.sub("", text)

    # more than one space
    text = EXTRA_SPACE.sub(" ", text)

    # remove all footnotes
    text = FOOTNOTES.sub("", text)

    # remove extraneous start that is not alphanumeric
    text = START_NOT_ALPHANUM.sub("", text)

    # remove extraneous end that is not alphanumeric
    text = END_NOT_ALPHANUM.sub("", text)

    return text


def is_too_short(text: str) -> bool:
    return len(text) <= MIN_LENGTH_CHARS_IN_LINE


def is_short_and_all_upper(text: str) -> bool:
    """See https://stackoverflow.com/a/69513831"""
    all_upper = all(map(NO_LOWERCASE.search, text.split(" ")))
    is_short = len(text) <= MIN_LENGTH_ALL_UPPER
    return all_upper and is_short


def is_fn_filler(text: str) -> bool:
    if FOOTNOTE_FILLER.search(text):
        return True
    return False


INVALID_TEXT_FUNCS = [is_too_short, is_fn_filler, is_short_and_all_upper]
"""Not utilized"""


def is_invalid(text: str) -> bool:
    return any(is_bad(text) for is_bad in INVALID_TEXT_FUNCS)


def validate_segment(text: str) -> str | None:
    # limit to body segments
    if is_too_short(text.strip()) or STARTS_WITH_FOOTNOTE.search(text.strip()):
        return None
    return clean_segment(text)
