import datetime
from pathlib import Path
from sqlite3 import IntegrityError

import yaml
from citation_utils import Citation
from loguru import logger
from markdownify import markdownify
from pydantic import BaseModel, Field, root_validator
from slugify import slugify

from .helpers import CourtComposition, DecisionCategory, DecisionSource
from .resources import DECISION_TBL


class DecisionRow(BaseModel):

    id: str
    created: float
    modified: float
    origin: str
    source: DecisionSource
    citation: Citation = Field(exclude=True)
    emails: str
    title: str
    description: str
    date: datetime.date
    raw_ponente: str | None = Field(None)
    per_curiam: bool = Field(
        False,
        title="Is Per Curiam",
        description="If true, decision was penned anonymously.",
    )
    composition: CourtComposition = Field(None)
    category: DecisionCategory = Field(None)
    fallo: str | None = Field(None)
    voting: str | None = Field(None)

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
        idx_prefix = "idx_cases_"
        indexes = [
            ["source", "origin", "date"],
            ["date"],
            ["source", "origin"],
            ["category", "composition"],
            ["per_curiam", "raw_ponente"],
            ["raw_ponente"],
            ["per_curiam"],
        ]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        tbl.enable_fts(
            ["voting", "title", "fallo"],
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
        from .ponente import RawPonente

        f = p.parent / "fallo.html"
        data = yaml.safe_load(p.read_text())
        citation = Citation.from_details(data)
        ponente = RawPonente.extract(data.get("ponente"))
        id = p.parent.name
        if p.parent.parent.stem == "legacy":
            id = citation.slug or p.parent.name
        elif citation.docket:
            id = slugify("-".join(citation.docket))
        if not citation.slug:
            logger.debug(f"Citation absent: {p=}")
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
            raw_ponente=ponente.writer if ponente else None,
            per_curiam=ponente.per_curiam if ponente else False,
            citation=citation,
            emails=", ".join(data.get("emails", ["bot@lawsql.com"])),
        )
