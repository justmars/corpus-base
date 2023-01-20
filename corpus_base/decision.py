import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from citation_utils import Citation, extract_citation_from_data
from dateutil.parser import parse
from loguru import logger
from markdownify import markdownify
from pydantic import Field, root_validator
from slugify import slugify
from sqlpyd import Connection, TableConfig

from .justice import Justice
from .utils import (
    CourtComposition,
    DecisionCategory,
    DecisionHTMLConvertMarkdown,
    DecisionSource,
    RawPonente,
    sc_jinja_env,
    voteline_clean,
)


class DecisionRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "decisions"
    __indexes__ = [
        ["date", "justice_id", "raw_ponente", "per_curiam"],
        ["source", "origin", "date"],
        ["source", "origin"],
        ["category", "composition"],
        ["id", "justice_id"],
        ["per_curiam", "raw_ponente"],
    ]

    id: str = Field(col=str)
    created: float = Field(col=float)
    modified: float = Field(col=float)
    origin: str = Field(col=str, index=True)
    source: DecisionSource = Field(col=str, index=True)
    citation: Citation = Field(exclude=True)
    emails: list[str] = Field(col=str)
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
        citation = extract_citation_from_data(data)
        id = cls.get_id_from_citation(
            folder_name=p.parent.name,
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
            emails=data.get("emails", ["bot@lawsql.com"]),
        )

    @classmethod
    def get_justice_id(
        cls,
        c: Connection,
        ponente: RawPonente | None,
        raw_date: str,
        path: Path,
    ) -> int | None:
        if not ponente or not raw_date:
            return None
        if not ponente.writer:
            return None

        try:
            conv_date = parse(raw_date).date().isoformat()
        except Exception as e:
            logger.error(f"Bad {raw_date=}; {e=} {path=}")
            return None

        candidates = c.db.execute_returning_dicts(
            sql=sc_jinja_env.get_template("get_justice_id.sql").render(
                justice_tbl=Justice.__tablename__,
                target_name=ponente.writer,
                target_date=conv_date,
            )
        )

        if not candidates:
            logger.error(f"No id: {ponente.writer=}; {conv_date=}; {path=}")
            return None

        elif len(candidates) > 1:
            logger.error(f"Multiple ids; similarity {candidates=}; {path=}")
            return None

        return candidates[0]["id"]

    @classmethod
    def get_id_from_citation(
        cls, folder_name: str, source: str, citation: Citation
    ) -> str:
        """The decision id to be used as a url slug ought to be unique,
        based on citation paramters if possible."""
        if not citation.slug:
            logger.debug(f"Citation absent: {source=}; {folder_name=}")
            return folder_name

        if source == "legacy":
            return citation.slug or folder_name

        elif citation.docket:
            if report := citation.scra or citation.phil:
                return slugify("-".join([citation.docket, report]))
            return slugify(citation.docket)
        return folder_name

    @property
    def citation_fk(self) -> dict:
        return self.citation.dict() | {"decision_id": self.id}


class CitationRow(Citation, TableConfig):
    __prefix__ = "sc"
    __tablename__ = "citations"
    __indexes__ = [
        ["id", "decision_id"],
        ["docket_category", "docket_serial", "docket_date"],
        ["scra", "phil", "offg", "docket"],
    ]
    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )


class VoteLine(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "votelines"
    __indexes__ = [["id", "decision_id"]]
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


class TitleTagRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "titletags"
    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )
    tag: str = Field(..., col=str, index=True)


class OpinionRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "opinions"
    __indexes__ = [
        ["id", "title"],
        ["id", "justice_id"],
        ["id", "decision_id"],
        ["decision_id", "title"],
    ]
    decision_id: str = Field(
        ..., col=str, fk=(DecisionRow.__tablename__, "id")
    )
    id: str = Field(
        ...,
        description="The opinion pk is based on combining the decision_id with the justice_id",
        col=str,
    )
    title: str | None = Field(
        ...,
        description="How is the opinion called, e.g. Ponencia, Concurring Opinion, Separate Opinion",
        col=str,
    )
    tags: list[str] | None = Field(
        None,
        description="e.g. main, dissenting, concurring, separate",
    )
    justice_id: int | None = Field(
        None,
        description="The writer of the opinion; when not supplied could mean a Per Curiam opinion, or unable to detect the proper justice.",
        col=int,
        index=True,
        fk=(Justice.__tablename__, "id"),
    )
    remark: str | None = Field(
        None,
        description="Short description of the opinion, when available, i.e. 'I reserve my right, etc.', 'On leave.', etc.",
        col=str,
        fts=True,
    )
    concurs: list[dict] | None
    text: str = Field(
        ..., description="Text proper of the opinion.", col=str, fts=True
    )

    @classmethod
    def get_opinions(
        cls,
        case_path: Path,
        decision_id: str,
        justice_id: int | None = None,
    ) -> Iterator:
        """Each opinion of a decision, except the ponencia, should be added separately.
        The format of the opinion should follow the form in test_data/legacy/tanada1."""
        ops = case_path / "opinions"
        for op in ops.glob("[!ponencia]*.md"):
            opinion = cls.extract_separate(case_path, decision_id, op)
            yield opinion
        if main := cls.extract_main(case_path, decision_id, justice_id):
            yield main

    @classmethod
    def extract_separate(
        cls, case_path: Path, decision_id: str, opinion_path: Path
    ):
        data = frontmatter.loads(opinion_path.read_text())
        return cls(
            id=f"{case_path.stem}-{opinion_path.stem}",
            title=data.get("title", None),
            tags=data.get("tags", []),
            decision_id=decision_id,
            justice_id=int(opinion_path.stem),
            remark=data.get("remark", None),
            concurs=data.get("concur", None),
            text=data.content,
        )

    @classmethod
    def extract_main(
        cls, case_path: Path, decision_id: str, justice_id: int | None = None
    ):
        try:  # option: add_markdown_file(case_path, md_txt.result)
            return cls(
                id=f"{case_path.stem}-main",
                title="Ponencia",
                tags=["main"],
                decision_id=decision_id,
                justice_id=justice_id,
                remark=None,
                concurs=None,
                text=DecisionHTMLConvertMarkdown(case_path).result,
            )
        except Exception as e:
            logger.error(f"Could not convert text {case_path.stem=}; see {e=}")
            return None

    @property
    def segments(self) -> Iterator[dict[str, Any]]:
        """Validate each segment and output its dict format."""
        from .segment import SegmentRow

        for extract in SegmentRow.segmentize(self.text):
            yield SegmentRow(
                id=f"{self.id}-{extract['position']}",
                decision_id=self.decision_id,
                opinion_id=self.id,
                **extract,
            ).dict()
