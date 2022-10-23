import re
from enum import Enum

CATEGORY_START_DECISION = re.compile(r"d\s*e\s*c", re.I)
CATEGORY_START_RESOLUTION = re.compile(r"r\s*e\s*s", re.I)
COMPOSITION_START_DIVISION = re.compile(r"div", re.I)
COMPOSITION_START_ENBANC = re.compile(r"en", re.I)


class DecisionSource(str, Enum):
    sc = "sc"
    legacy = "legacy"


class DecisionCategory(str, Enum):
    decision = "Decision"
    resolution = "Resolution"
    other = "Unspecified"

    @classmethod
    def _setter(cls, text: str | None):

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

        if text:
            if COMPOSITION_START_DIVISION.search(text):
                return cls.division
            elif COMPOSITION_START_ENBANC.search(text):
                return cls.enbanc
        return cls.other
