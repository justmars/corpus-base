from pathlib import Path
from typing import Iterator

import frontmatter
from loguru import logger
from pydantic import BaseModel, Field
from sqlpyd import Connection, TableConfig

from .decision import DecisionRow
from .justice import Justice
from .utils import DecisionHTMLConvertMarkdown


class OpinionRow(BaseModel, TableConfig):
    __tablename__ = "sc_decisions_opinions_tbl"

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
    decision_id: str = Field(
        ...,
        description="Each opinion belongs to a decision id",
        col=str,
        index=True,
        fk=(DecisionRow.__tablename__, "id"),
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
    def make_table(cls, c: Connection):
        return cls.config_tbl(
            tbl=c.tbl(cls.__tablename__),
            cols=cls.__fields__,
            idxs=[
                ["id", "title"],
                ["id", "justice_id"],
                ["id", "decision_id"],
                ["decision_id", "title"],
            ],
        )

    @classmethod
    def get_opinions(
        cls, case_path: Path, justice_id: int | None = None
    ) -> Iterator:
        """Each opinion of a decision, except the ponencia, should be added separately. The format of the opinion should follow the form in test_data/legacy/tanada1."""
        ops = case_path / "opinions"
        for op in ops.glob("[!ponencia]*.md"):
            opinion = cls.extract_separate_opinion(case_path, op)
            yield opinion
        if main := cls.extract_main_opinion(case_path, justice_id):
            yield main

    @classmethod
    def extract_separate_opinion(cls, case_path: Path, opinion_path: Path):
        op_pk = f"{case_path.stem}-{opinion_path.stem}"
        data = frontmatter.loads(opinion_path.read_text())
        text = data.content
        return cls(
            id=op_pk,
            title=data.get("title", None),
            tags=data.get("tags", []),
            decision_id=case_path.stem,
            justice_id=int(opinion_path.stem),
            remark=data.get("remark", None),
            concurs=data.get("concur", None),
            text=text,
        )

    @classmethod
    def extract_main_opinion(
        cls, case_path: Path, justice_id: int | None = None
    ):
        try:
            op_pk = f"{case_path.stem}-main"
            md_txt = DecisionHTMLConvertMarkdown(case_path)
            # add_markdown_file(case_path, md_txt.result)
            text = md_txt.result
            return cls(
                id=op_pk,
                title="Ponencia",
                tags=["main"],
                decision_id=case_path.stem,
                justice_id=justice_id,
                remark=None,
                concurs=None,
                text=text,
            )
        except Exception as e:
            logger.error(f"Could not convert text {case_path.stem=}; see {e=}")
            return None
