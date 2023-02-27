import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Self

import frontmatter
from citation_utils import Citation
from corpus_pax import Individual
from corpus_sc_toolkit import (
    BaseDecision,
    CourtComposition,
    DecisionCategory,
    DecisionHTMLConvertMarkdown,
    DecisionSource,
    InterimDecision,
    Justice,
    extract_votelines,
    segmentize,
    tags_from_title,
)
from loguru import logger
from pydantic import Field, root_validator
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
    is_pdf: bool | None = Field(False, col=bool, index=True)

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
    def from_path(cls, c: Connection, p: Path) -> Self | None:
        obj = BaseDecision.from_path(path=p, db=c.db)
        return cls(**obj.dict()) if obj else None

    @classmethod
    def from_pdf(cls, obj: InterimDecision) -> Self | None:
        return cls(**obj.dict())

    @property
    def citation_fk(self) -> dict:
        return self.citation.dict() | {"decision_id": self.id}

    def add_meta(self, conn: Connection) -> str | None:
        """This creates a decision row and correlated metadata involving
        the decision, i.e. the citation, voting text, tags from the title, etc.,
        and then add rows for their respective tables.

        Args:
            conn (Connection): sqlpyd wrapper over sqlite_utils
            decision (DecisionRow): Uniform fields ready for database insertion

        Returns:
            str | None: The decision id, if the insertion of records is successful.
        """

        try:
            pk = (
                conn.table(DecisionRow)
                .insert(record=self.dict(), pk="id")  # type: ignore
                .last_pk
            )
            logger.debug(f"Added {pk=}")
        except Exception as e:
            logger.error(f"Skipping duplicate {self=}; {e=}")
            return None
        if not pk:
            logger.error(f"Could not find decision_id for {self=}")
            return None

        # Assign author row to a joined m2m table, note the explicit m2m table name
        # so that the prefix used is `sc_`.
        for email in self.emails:
            conn.table(DecisionRow).update(pk).m2m(
                other_table=conn.table(Individual),
                pk="id",
                lookup={"email": email},
                m2m_table="sc_tbl_decisions_pax_tbl_individuals",
            )

        # add associated citation
        if self.citation and self.citation.has_citation:
            conn.add_record(
                kls=CitationRow,
                item=self.citation_fk,
            )

        # process votelines of voting text in decision
        if self.voting:
            conn.add_records(
                kls=VoteLine,
                items=extract_votelines(decision_pk=pk, text=self.voting),
            )

        # add tags based on title of decision
        if self.title:
            conn.add_records(
                kls=TitleTagRow,
                items=tags_from_title(decision_pk=pk, text=self.title),
            )
        return self.id


DECISION_ID = Field(
    default=...,
    title="Decision ID",
    description=(
        "Foreign key used by other tables referencing the Decision table."
    ),
    col=str,
    fk=(DecisionRow.__tablename__, "id"),
)


class CitationRow(Citation, TableConfig):
    __prefix__ = "sc"
    __tablename__ = "citations"
    __indexes__ = [
        ["id", "decision_id"],
        ["docket_category", "docket_serial", "docket_date"],
        ["scra", "phil", "offg", "docket"],
    ]
    decision_id: str = DECISION_ID


class VoteLine(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "votelines"
    __indexes__ = [["id", "decision_id"]]
    decision_id: str = DECISION_ID
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
    decision_id: str = DECISION_ID
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
    decision_id: str = DECISION_ID
    id: str = Field(
        ...,
        description=(
            "The opinion pk is based on combining the decision_id with the"
            " justice_id"
        ),
        col=str,
    )
    pdf: str | None = Field(
        default=None,
        description=(
            "The opinion pdf is the url that links to the downloadable PDF, if"
            " it exists"
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
        default=None,
        description="e.g. main, dissenting, concurring, separate",
    )
    justice_id: int | None = Field(
        default=None,
        description=(
            "The writer of the opinion; when not supplied could mean a Per"
            " Curiam opinion, or unable to detect the proper justice."
        ),
        col=int,
        index=True,
        fk=(Justice.__tablename__, "id"),
    )
    remark: str | None = Field(
        default=None,
        description=(
            "Short description of the opinion, when available, i.e. 'I reserve"
            " my right, etc.', 'On leave.', etc."
        ),
        col=str,
        fts=True,
    )
    concurs: list[dict] | None = Field(default=None)
    text: str = Field(
        ...,
        description=(
            "Text proper of the opinion (should ideally be in markdown format)"
        ),
        col=str,
        fts=True,
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


class SegmentRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "segments"
    __indexes__ = [["opinion_id", "decision_id"]]
    id: str = Field(..., col=str)
    decision_id: str = DECISION_ID
    opinion_id: str = Field(..., col=str, fk=(OpinionRow.__tablename__, "id"))
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
