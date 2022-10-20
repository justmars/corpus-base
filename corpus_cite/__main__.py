import datetime
import os
import re
import sys
from enum import Enum
from pathlib import Path
from sqlite3 import IntegrityError

import yaml
from citation_utils import Citation
from dateutil.parser import parse
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from markdownify import markdownify
from pydantic import BaseModel, Field
from slugify import slugify

load_dotenv(find_dotenv())


logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "{message}",
            "level": "ERROR",
        },
        {
            "sink": "logs/decision.log",
            "format": "{message}",
            "level": "WARNING",
            "serialize": True,
        },
    ]
)
SRC_FILES = os.getenv("SRC_FILES", "code/corpus/decisions/**/*/details.yaml")
DECISION_TBL = os.getenv("DECISION_TBL", "decisions_tbl")
CITATION_TBL = os.getenv("CITATION_TBL", "decision_citations_tbl")
VOTELINE_TBL = os.getenv("VOTELINE_TBL", "decision_votelines_tbl")
TITLETAG_TBL = os.getenv("TITLETAG_TBL", "decision_tags_tbl")
CATEGORY_START_DECISION = re.compile(r"d\s*e\s*c", re.I)
CATEGORY_START_RESOLUTION = re.compile(r"r\s*e\s*s", re.I)
COMPOSITION_START_DIVISION = re.compile(r"div", re.I)
COMPOSITION_START_ENBANC = re.compile(r"en", re.I)
IS_PER_CURIAM = re.compile(r"per\s+curiam", re.I)


class DecisionSource(str, Enum):
    """Source of scraping the decision."""

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


class CitationRow(Citation):
    """Each Citation is associated with a decision."""

    decision_id: str

    @classmethod
    def make_table(cls, db):
        tbl = db[CITATION_TBL]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={
                "id": int,
                "decision_id": str,
                "scra": str,
                "phil": str,
                "offg": str,
                "docket": str,
                "docket_category": str,
                "docket_serial": str,
                "docket_date": str,
            },
            pk="id",
            foreign_keys=[("decision_id", DECISION_TBL, "id")],
            if_not_exists=True,
        )
        idx_prefix = "idx_cites_"
        indexes = [
            ["id", "decision_id"],
            ["docket_category", "docket_serial", "docket_date"],
            ["scra", "phil", "offg", "docket"],
            ["offg"],
            ["scra"],
            ["phil"],
            ["docket"],
        ]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        return tbl

    @classmethod
    def insert_row(cls, db, item: dict):
        tbl = cls.make_table(db)
        tbl.insert(item)


class VoteLine(BaseModel):
    """Each decision may contain a vote line, e.g. a summary of which justice voted for the main opinion and those who dissented, etc."""

    decision_id: str
    text: str

    @classmethod
    def make_table(cls, db):
        tbl = db[VOTELINE_TBL]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={"id": int, "decision_id": str, "text": str},
            pk="id",
            foreign_keys=[("decision_id", DECISION_TBL, "id")],
            if_not_exists=True,
        )
        idx_prefix = "idx_votes_"
        indexes = [["id", "decision_id"]]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        tbl.enable_fts(
            ["text"],
            create_triggers=True,
            replace=True,
            tokenize="porter",
        )
        return tbl

    @classmethod
    def insert_rows(cls, db, items: list["VoteLine"]):
        if items:
            tbl = cls.make_table(db)
            rows = [i.dict() for i in items]
            for row in rows:
                tbl.insert(row)

    @classmethod
    def extract_lines(cls, pk: str, text: str):
        from .helpers import is_line_ok

        for line in text.splitlines():
            if is_line_ok(line):
                yield cls(decision_id=pk, text=line)


class DecisionRow(BaseModel):

    id: str
    created: float
    modified: float
    origin: str
    source: DecisionSource
    citation: Citation = Field(exclude=True)
    emails: str
    title: str
    description: str = Field("Sample")
    date: datetime.date
    raw_ponente: str = Field(None)
    per_curiam: bool = Field(
        False,
        title="Is Per Curiam",
        description="If true, decision was penned anonymously.",
    )
    composition: CourtComposition = Field(None)
    category: DecisionCategory = Field(None)
    fallo: str | None = Field(None)
    voting: str | None = Field(None)

    class Config:
        use_enum_values = True

    @classmethod
    def make_table(cls, db):
        tbl = db[DECISION_TBL]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={
                "id": str,
                "created": str,
                "modified": str,
                "emails": str,  # comma separated emails for later use
                "origin": str,
                "source": str,
                "title": str,
                "description": str,
                "date": datetime.date,
                "fallo": str,
                "voting": str,
                "category": str,
                "composition": str,
                "per_curiam": bool,
                "raw_ponente": str,  # what appears on file
            },
            pk="id",
            if_not_exists=True,
        )
        tbl.enable_fts(
            ["title", "fallo"],
            create_triggers=True,
            replace=True,
            tokenize="porter",
        )
        return tbl

    @classmethod
    def insert_row(cls, db, item: dict):
        tbl = cls.make_table(db)
        try:
            tbl.insert(item)
        except IntegrityError as e:
            msg = f"Skipping duplicate {item=}; {e=}"
            logger.error(msg)

    @classmethod
    def from_path(cls, p: Path):
        """Requires path be structured, viz.:

        - /decisions
            - /source e.g. sc / legacy <-- where the file was scraped from
                - /folder_name, e.g. 12341 <-- the original id when scraped
                    - /details.yaml <-- the file containing the metadata that is `p`
        """
        from .helpers import voteline_clean
        from .ponente import clean_raw_ponente

        data = yaml.safe_load(p.read_text())
        citation = Citation.from_details(data)

        per_curiam = False
        ponente = None
        if ponente := data.get("ponente"):
            ponente = ponente.strip()
            if ponente:
                if IS_PER_CURIAM.search(ponente):
                    per_curiam = True
                    ponente = None
                else:
                    if len(ponente) >= 3:
                        ponente = clean_raw_ponente(ponente)

        emails = data.get("emails", ["bot@lawsql.com"])
        emails = ", ".join(emails)

        title = data.get("case_title")
        if not title:
            msg = f"No case title: {p=}"
            logger.warning(msg)
            raise Exception(msg)

        voting = None
        if voting := data.get("voting"):
            voting = voting.lstrip(". ").rstrip("")
            if voting:
                if 15 < len(voting):
                    voting = voteline_clean(voting)
                else:
                    msg = f"Unlikely {voting=} {p=}"
                    logger.warning(msg)
        else:
            msg = f"No voting: {p=}"
            logger.warning(msg)

        fallo_file = p.parent / "fallo.html"
        fallo = None
        if fallo_file.exists():
            fallo = markdownify(fallo_file.read_text())

        date_obj = None
        if date_prom := data.get("date_prom"):
            date_obj = parse(date_prom).date()
            if citation.docket_date and citation.docket.date != date_obj:
                msg = f"Inconsistent {citation=}; details.yaml {date_obj=}; see {p=}"
                logger.warning(msg)
                raise Exception(msg)
            modern_sc_date = datetime.date(year=1996, month=1, day=1)
            if p.parent.parent.stem == "legacy" and date_obj >= modern_sc_date:
                msg = f"{p=} has {date_obj=}; note {modern_sc_date=} {p=}"
                logger.error(msg)
                raise Exception(msg)

        id = p.parent.name
        if p.parent.parent.stem == "legacy":
            id = citation.slug or p.parent.name
        else:  # modern sc decisions
            if citation.docket:
                id = slugify("-".join(citation.docket))
        if not citation.slug:
            logger.warning(f"Citation absent: {p=}")
        return cls(
            id=id,
            origin=p.parent.name,
            source=p.parent.parent.stem,
            created=p.stat().st_ctime,
            modified=p.stat().st_mtime,
            title=title,
            date=date_obj,
            composition=CourtComposition._setter(data.get("composition")),
            category=DecisionCategory._setter(data.get("category")),
            fallo=fallo,
            voting=voting,
            raw_ponente=ponente,
            per_curiam=per_curiam,
            citation=citation,
            emails=emails,
        )
