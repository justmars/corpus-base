import re
from enum import Enum

from markdownify import markdownify


class DecisionSource(str, Enum):
    sc = "sc"
    legacy = "legacy"


class DecisionCategory(str, Enum):
    decision = "Decision"
    resolution = "Resolution"
    other = "Unspecified"

    @classmethod
    def _setter(cls, text: str | None):
        from .resources import (
            CATEGORY_START_DECISION,
            CATEGORY_START_RESOLUTION,
        )

        if text:
            if CATEGORY_START_DECISION.search(text):
                return cls.decision
            elif CATEGORY_START_RESOLUTION.search(text):
                return cls.resolution
        return cls.other


class CourtComposition(str, Enum):
    enbanc = "En Banc"
    division = "Division"
    other = "Unspecified"

    @classmethod
    def _setter(cls, text: str | None):
        from .resources import (
            COMPOSITION_START_DIVISION,
            COMPOSITION_START_ENBANC,
        )

        if text:
            if COMPOSITION_START_DIVISION.search(text):
                return cls.division
            elif COMPOSITION_START_ENBANC.search(text):
                return cls.enbanc
        return cls.other


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
    from .resources import VOTEFULL_MIN_LENGTH

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
    from .resources import VOTELINE_MAX_LENGTH, VOTELINE_MIN_LENGTH

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
