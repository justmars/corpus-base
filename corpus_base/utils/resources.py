import re
from collections.abc import Iterator
from enum import Enum
from http import HTTPStatus
from pathlib import Path

import yaml
from corpus_pax._api import GithubAccess
from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger

CHIEF_DATES_VIEW = "chief_dates"
MAX_JUSTICE_AGE = 70

_DECISIONS = "code/corpus/decisions"
DECISION_PATH = Path().home().joinpath(_DECISIONS)

JUSTICE_LOCAL = Path(__file__).parent / "sc.yaml"


sc_jinja_env = Environment(
    loader=PackageLoader(package_name="corpus_base"),
    autoescape=select_autoescape(),
)


def get_justices_from_api() -> Iterator[dict]:
    gh = GithubAccess()  # type: ignore
    url = "https://api.github.com/repos/justmars/corpus/contents/justices/sc.yaml"
    resp = gh.fetch(url)
    if not resp:
        raise Exception(f"No response, check {url=}")
    if not resp.status_code == HTTPStatus.OK:
        raise Exception(f"{resp.status_code=}, see settings.")
    yield from yaml.safe_load(resp.content)


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


logger.configure(
    handlers=[
        {
            "sink": "logs/error.log",
            "format": "{message}",
            "level": "ERROR",
        },
        {
            "sink": "logs/warnings.log",
            "format": "{message}",
            "level": "WARNING",
            "serialize": True,
        },
    ]
)
