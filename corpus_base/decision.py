import datetime
from pathlib import Path

import yaml
from citation_utils import Citation
from dateutil.parser import parse
from loguru import logger
from markdownify import markdownify
from pydantic import BaseModel, Field, root_validator
from slugify import slugify
from sqlpyd import Connection, TableConfig

from .justice import Justice
from .settings import settings
from .utils import (
    CourtComposition,
    DecisionCategory,
    DecisionSource,
    RawPonente,
    voteline_clean,
)


class DecisionRow(BaseModel, TableConfig):
    __tablename__ = "sc_decisions_tbl"

    id: str = Field(col=str)
    created: float = Field(col=float)
    modified: float = Field(col=float)
    origin: str = Field(col=str, index=True)
    source: DecisionSource = Field(col=str, index=True)
    citation: Citation = Field(exclude=True)
    emails: str = Field(col=str)
    title: str = Field(col=str, index=True, fts=True)
    description: str = Field(col=str, index=True, fts=True)
    date: datetime.date = Field(col=datetime.date, index=True)
    raw_ponente: str | None = Field(
        None,
        title="Ponente",
        description="After going through a cleaning process, this should be in lowercase and be suitable for matching a justice id.",
        col=str,
        index=True,
    )
    justice_id: int | None = Field(
        None,
        title="Justice ID",
        description="Using the raw_ponente, determine the appropriate justice_id using the `update_justice_ids.sql` template.",
        col=int,
        index=True,
    )
    per_curiam: bool = Field(
        False,
        title="Is Per Curiam",
        description="If true, decision was penned anonymously.",
        col=bool,
        index=True,
    )
    composition: CourtComposition = Field(None, col=str, index=True)
    category: DecisionCategory = Field(None, col=str, index=True)
    fallo: str | None = Field(None, col=str, index=True, fts=True)
    voting: str | None = Field(None, col=str, index=True, fts=True)

    @root_validator()
    def citation_date_is_object_date(cls, values):
        cite, date = values.get("citation"), values.get("date")
        if cite.docket_date:
            if cite.docket_date != date:
                msg = f"Inconsistent {cite.docket_date=} vs. {date=};"
                logger.error(msg)
                raise ValueError(msg)
        return values

    @root_validator()
    def legacy_upto_1995(cls, values):
        source, date = values.get("source"), values.get("date")
        if source == "legacy":
            if date and date > datetime.date(year=1995, month=12, day=31):
                msg = "Improper parsing of legacy decision"
                logger.error(msg)
                raise ValueError(msg)
        return values

    class Config:
        use_enum_values = True

    @classmethod
    def make_table(cls, c: Connection):
        return cls.config_tbl(
            tbl=c.tbl(cls.__tablename__),
            cols=cls.__fields__,
            idxs=[
                ["date", "justice_id", "raw_ponente", "per_curiam"],
                ["source", "origin", "date"],
                ["source", "origin"],
                ["category", "composition"],
                ["id", "justice_id"],
                ["per_curiam", "raw_ponente"],
            ],
        )

    @classmethod
    def from_path(cls, c: Connection, p: Path):
        """Requires path be structured, viz.:

        - /decisions
            - /source e.g. sc / legacy <-- where the file was scraped from
                - /folder_name, e.g. 12341 <-- the original id when scraped
                    - /details.yaml <-- the file containing the metadata that is `p`
        """

        f = p.parent / "fallo.html"
        data = yaml.safe_load(p.read_text())
        pon = RawPonente.extract(data.get("ponente"))
        citation = Citation.from_details(data)
        id = cls.get_id_from_citation(
            original_folder_name=p.parent.name,
            source=p.parent.parent.stem,
            citation=citation,
        )
        return cls(
            id=id,
            origin=p.parent.name,
            source=DecisionSource(p.parent.parent.stem),
            created=p.stat().st_ctime,
            modified=p.stat().st_mtime,
            title=data.get("case_title"),
            description=citation.display,
            date=data.get("date_prom"),
            composition=CourtComposition._setter(data.get("composition")),
            category=DecisionCategory._setter(data.get("category")),
            fallo=markdownify(f.read_text()) if f.exists() else None,
            voting=voteline_clean(data.get("voting")),
            raw_ponente=pon.writer if pon else None,
            justice_id=cls.get_justice_id(c, pon, data.get("date_prom"), p),
            per_curiam=pon.per_curiam if pon else False,
            citation=citation,
            emails=", ".join(data.get("emails", ["bot@lawsql.com"])),
        )

    @classmethod
    def get_justice_id(
        cls,
        c: Connection,
        ponente: RawPonente | None,
        raw_date: str,
        path: Path,
    ) -> int | None:
        if not ponente:
            return None
        if not ponente.writer:
            return None
        if not raw_date:
            return None
        try:
            converted_date = parse(raw_date).date().isoformat()
        except Exception as e:
            logger.error(f"Bad {raw_date=}; {e=} {path=}")
            return None

        candidates = c.db.execute_returning_dicts(
            sql=settings.sc_env.get_template("get_justice_id.sql").render(
                justice_tbl=Justice.__tablename__,
                target_name=ponente.writer,
                target_date=converted_date,
            )
        )

        if not candidates:
            msg = f"No id: {ponente.writer=}; {converted_date=}; {path=}"
            logger.error(msg)
            return None

        elif len(candidates) > 1:
            msg = f"Multiple ids; similarity {candidates=}; {path=}"
            logger.error(msg)
            return None

        return candidates[0]["id"]

    @classmethod
    def get_id_from_citation(
        cls,
        original_folder_name: str,
        source: str,
        citation: Citation,
    ) -> str:
        """The decision id to be used as a url slug ought to be unique, based on citation paramters if possible."""
        if not citation.slug:
            msg = f"Citation absent: {source=}; {original_folder_name=}"
            logger.debug(msg)
            return original_folder_name

        if source == "legacy":
            return citation.slug or original_folder_name

        elif citation.docket:
            if report := citation.scra or citation.phil:
                return slugify("-".join([citation.docket, report]))
            return slugify(citation.docket)

        return original_folder_name

    @property
    def citation_fk(self) -> dict:
        return self.citation.dict() | {"decision_id": self.id}


class CitationRow(Citation, TableConfig):
    __tablename__ = "sc_decisions_citations_tbl"

    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )

    @classmethod
    def make_table(cls, c: Connection):
        return cls.config_tbl(
            tbl=c.tbl(cls.__tablename__),
            cols=cls.__fields__,
            idxs=[
                ["id", "decision_id"],
                ["docket_category", "docket_serial", "docket_date"],
                ["scra", "phil", "offg", "docket"],
            ],
        )


class VoteLine(BaseModel, TableConfig):
    __tablename__ = "sc_decisions_votelines_tbl"

    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )
    text: str = Field(
        ...,
        title="Voteline Text",
        description="Each decision may contain a vote line, e.g. a summary of which justice voted for the main opinion and those who dissented, etc.",
        col=str,
        index=True,
    )

    @classmethod
    def make_table(cls, c: Connection):
        return cls.config_tbl(
            tbl=c.tbl(cls.__tablename__),
            cols=cls.__fields__,
            idxs=[["id", "decision_id"]],
        )


class TitleTagRow(BaseModel, TableConfig):
    __tablename__ = "sc_decisions_titletags_tbl"

    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )
    tag: str = Field(..., col=str, index=True)

    @classmethod
    def make_table(cls, c: Connection):
        return cls.config_tbl(
            tbl=c.tbl(cls.__tablename__), cols=cls.__fields__
        )
