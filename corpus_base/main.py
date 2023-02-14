import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from citation_utils import Citation
from corpus_pax import Individual
from corpus_sc_toolkit import (
    CandidateJustice,
    CourtComposition,
    DecisionCategory,
    DecisionHTMLConvertMarkdown,
    DecisionSource,
    Justice,
    extract_votelines,
    get_id_from_citation,
    get_justices_file,
    segmentize,
    tags_from_title,
    voteline_clean,
)
from corpus_sc_toolkit.resources import DECISION_PATH
from loguru import logger
from markdownify import markdownify
from pydantic import Field, root_validator
from sqlite_utils.db import Database
from sqlpyd import Connection, TableConfig


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
        description=(
            "After going through a cleaning process, this should be in"
            " lowercase and be suitable for matching a justice id."
        ),
        col=str,
        index=True,
    )
    justice_id: int | None = Field(
        None,
        title="Justice ID",
        description=(
            "Using the raw_ponente, determine the appropriate justice_id using"
            " the `update_justice_ids.sql` template."
        ),
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

        ```yaml
        - /decisions
            - /source e.g. sc / legacy # where the file was scraped from
                - /folder_name, e.g. 12341 # the original id when scraped
                    - /details.yaml #the file containing the metadata that is `p`
        ```
        """

        f = p.parent / "fallo.html"
        data = yaml.safe_load(p.read_text())
        candidate = CandidateJustice(
            db=c.db,
            text=data.get("ponente"),
            date_str=data.get("date_prom"),
        )
        justice_fields = (
            candidate.detail._asdict()
            if candidate and candidate.detail
            else {"raw_ponente": None, "per_curiam": False, "justice_id": None}
        )
        cite = Citation.extract_citation_from_data(data)
        return cls(
            id=get_id_from_citation(
                folder_name=p.parent.name,
                source=p.parent.parent.stem,
                citation=cite,
            ),
            origin=p.parent.name,
            source=DecisionSource(p.parent.parent.stem),
            created=p.stat().st_ctime,
            modified=p.stat().st_mtime,
            title=data.get("case_title"),
            description=cite.display,
            date=data.get("date_prom"),
            composition=CourtComposition._setter(data.get("composition")),
            category=DecisionCategory._setter(data.get("category")),
            fallo=markdownify(f.read_text()) if f.exists() else None,
            voting=voteline_clean(data.get("voting")),
            citation=cite,
            emails=data.get("emails", ["bot@lawsql.com"]),
            **justice_fields,
        )

    @property
    def citation_fk(self) -> dict:
        return self.citation.dict() | {"decision_id": self.id}

    @classmethod
    def as_fk(cls) -> tuple[str, str]:
        return (cls.__tablename__, "id")


class CitationRow(Citation, TableConfig):
    __prefix__ = "sc"
    __tablename__ = "citations"
    __indexes__ = [
        ["id", "decision_id"],
        ["docket_category", "docket_serial", "docket_date"],
        ["scra", "phil", "offg", "docket"],
    ]
    decision_id: str = Field(..., col=str, fk=DecisionRow.as_fk())


class VoteLine(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "votelines"
    __indexes__ = [["id", "decision_id"]]
    decision_id: str = Field(..., col=str, fk=DecisionRow.as_fk())
    text: str = Field(
        ...,
        title="Voteline Text",
        description=(
            "Each decision may contain a vote line, e.g. a summary of which"
            " justice voted for the main opinion and those who dissented, etc."
        ),
        col=str,
        index=True,
    )


class TitleTagRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "titletags"
    decision_id: str = Field(..., col=str, fk=DecisionRow.as_fk())
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
    decision_id: str = Field(..., col=str, fk=DecisionRow.as_fk())
    id: str = Field(
        ...,
        description=(
            "The opinion pk is based on combining the decision_id with the"
            " justice_id"
        ),
        col=str,
    )
    title: str | None = Field(
        ...,
        description=(
            "How is the opinion called, e.g. Ponencia, Concurring Opinion,"
            " Separate Opinion"
        ),
        col=str,
    )
    tags: list[str] | None = Field(
        None,
        description="e.g. main, dissenting, concurring, separate",
    )
    justice_id: int | None = Field(
        None,
        description=(
            "The writer of the opinion; when not supplied could mean a Per"
            " Curiam opinion, or unable to detect the proper justice."
        ),
        col=int,
        index=True,
        fk=(Justice.__tablename__, "id"),
    )
    remark: str | None = Field(
        None,
        description=(
            "Short description of the opinion, when available, i.e. 'I reserve"
            " my right, etc.', 'On leave.', etc."
        ),
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
        The format of the opinion should follow the form in test_data/legacy/tanada1.
        """
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
        for extract in segmentize(self.text):
            yield SegmentRow(
                id=f"{self.id}-{extract['position']}",
                decision_id=self.decision_id,
                opinion_id=self.id,
                **extract,
            ).dict()

    @classmethod
    def as_fk(cls) -> tuple[str, str]:
        return (cls.__tablename__, "id")


class SegmentRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "segments"
    __indexes__ = [
        ["opinion_id", "decision_id"],
    ]
    id: str = Field(..., col=str)
    decision_id: str = Field(..., col=str, fk=DecisionRow.as_fk())
    opinion_id: str = Field(..., col=str, fk=OpinionRow.as_fk())
    position: str = Field(
        ...,
        title="Relative Position",
        description=(
            "The line number of the text as stripped from its markdown source."
        ),
        col=int,
        index=True,
    )
    char_count: int = Field(
        ...,
        title="Character Count",
        description=(
            "The number of characters of the text makes it easier to discover"
            " patterns."
        ),
        col=int,
        index=True,
    )
    segment: str = Field(
        ...,
        title="Body Segment",
        description=(
            "A partial text fragment of an opinion, exclusive of footnotes."
        ),
        col=str,
        fts=True,
    )


def build_sc_tables(c: Connection) -> Connection:
    c.add_records(Justice, yaml.safe_load(get_justices_file().read_bytes()))
    c.create_table(DecisionRow)
    c.create_table(CitationRow)
    c.create_table(OpinionRow)
    c.create_table(VoteLine)
    c.create_table(TitleTagRow)
    c.create_table(SegmentRow)
    c.db.index_foreign_keys()
    return c


def setup_case(c: Connection, path: Path) -> None:
    """Parse a case's `details.yaml` found in the `path`
    to generate rows for various `sc_tbl` prefixed sqlite tables found.

    After creation a decision row, get correlated metadata involving
    the decision: the citation, voting text, tags from the title, etc.,
    and then add rows for their respective tables.

    Args:
        c (Connection): sqlpyd Connection
        path (Path): path to a case's details.yaml
    """

    # initialize content from the path
    case_tbl = c.table(DecisionRow)
    obj = DecisionRow.from_path(c, path)

    try:
        decision_id = case_tbl.insert(obj.dict(), pk="id").last_pk  # type: ignore
        logger.debug(f"Added {decision_id=}")
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        logger.error(f"Could not find decision_id for {obj=}")
        return

    # assign author row to a joined m2m table, note the explicit m2m table name
    # so that the prefix used is `sc`; the default will start with `pax_`
    for email in obj.emails:
        case_tbl.update(decision_id).m2m(
            other_table=c.table(Individual),
            pk="id",
            lookup={"email": email},
            m2m_table="sc_tbl_decisions_pax_tbl_individuals",
        )

    # add associated citation
    if obj.citation and obj.citation.has_citation:
        c.add_record(CitationRow, obj.citation_fk)

    # process votelines of voting text in decision
    if obj.voting:
        c.add_records(VoteLine, extract_votelines(decision_id, obj.voting))

    # add tags based on the title of decision
    if obj.title:
        c.add_records(TitleTagRow, tags_from_title(decision_id, obj.title))

    # add opinions and segments
    for op in OpinionRow.get_opinions(
        case_path=path.parent,
        decision_id=decision_id,
        justice_id=case_tbl.get(decision_id).get("justice_id"),
    ):
        c.add_record(OpinionRow, op.dict(exclude={"concurs", "tags"}))
        c.add_records(SegmentRow, op.segments)


def add_authors_only(c: Connection):
    """Helper function for just adding the author decision m2m table."""
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for detail_path in case_details:
        obj = DecisionRow.from_path(c, detail_path)
        for email in obj.emails:  # assign author row to a joined m2m table
            tbl = c.table(DecisionRow)
            if tbl.get(obj.id):
                tbl.update(obj.id).m2m(
                    other_table=c.table(Individual),
                    lookup={"email": email},
                    pk="id",
                    m2m_table="sc_tbl_decisions_pax_tbl_individuals",
                )


def add_cases(c: Connection, test_only: int = 0) -> Database:
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for idx, details_file in enumerate(case_details):
        if test_only and idx == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)
    return c.db
