import datetime
from pathlib import Path

import yaml
from citation_utils import Citation
from dateutil.parser import parse
from loguru import logger
from markdownify import markdownify
from pydantic import BaseModel, Field, root_validator
from slugify import slugify

from .settings import settings
from .utils import (
    CourtComposition,
    DecisionCategory,
    DecisionSource,
    RawPonente,
    voteline_clean,
)

case_tbl = settings.tbl_decision


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
    raw_ponente: str | None = Field(
        None,
        title="Ponente",
        description="After going through a cleaning process, this should be in lowercase and be suitable for matching a justice id.",
    )
    justice_id: int | None = Field(
        None,
        title="Justice ID",
        description="Using the raw_ponente, determine the appropriate justice_id using the `update_justice_ids.sql` template.",
    )
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
    def make_table(cls):
        case_tbl.create(
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
                "justice_id": int,  # initially null
            },
            pk="id",
            if_not_exists=True,
        )
        settings.add_indexes(
            case_tbl,
            [
                ["source", "origin", "date"],
                ["date"],
                ["source", "origin"],
                ["category", "composition"],
                ["id", "justice_id"],
                ["date", "justice_id", "raw_ponente", "per_curiam"],
                ["per_curiam", "raw_ponente"],
                ["raw_ponente"],
                ["per_curiam"],
            ],
        )
        settings.add_fts(case_tbl, ["voting", "title", "fallo"])
        return case_tbl

    @classmethod
    def from_path(cls, p: Path):
        """Requires path be structured, viz.:

        - /decisions
            - /source e.g. sc / legacy <-- where the file was scraped from
                - /folder_name, e.g. 12341 <-- the original id when scraped
                    - /details.yaml <-- the file containing the metadata that is `p`
        """

        f = p.parent / "fallo.html"
        data = yaml.safe_load(p.read_text())
        citation = Citation.from_details(data)
        ponente = RawPonente.extract(data.get("ponente"))
        return cls(
            id=cls.setup_id_from_citation(
                original_folder_name=p.parent.name,
                source=p.parent.parent.stem,
                citation=citation,
            ),
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
            justice_id=cls.get_justice_id(ponente, data),
            per_curiam=ponente.per_curiam if ponente else False,
            citation=citation,
            emails=", ".join(data.get("emails", ["bot@lawsql.com"])),
        )

    @classmethod
    def get_justice_id(
        cls, ponente: RawPonente | None, data: dict
    ) -> int | None:
        raw_date = data.get("date_prom")
        if not ponente:
            return None
        if not ponente.writer:
            return None
        if not raw_date:
            return None
        try:
            converted_date = parse(raw_date).date().isoformat()
        except Exception as e:
            logger.error(f"Bad {raw_date=}")
            return None
        path = (
            Path()
            .home()
            .joinpath(
                settings.DecisionSourceFiles, data["source"], data["origin"]
            )
        )

        candidates = settings.db.execute_returning_dicts(
            sql=settings.base_env.get_template("get_justice_id.sql").render(
                justice_tbl=settings.JusticeTableName,
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

    def update_justice_ids(self):
        template = settings.base_env.get_template("update_justice_ids.sql")
        sql = template.render(
            justice_tbl=settings.JusticeTableName,
            decision_tbl=settings.DecisionTableName,
        )
        return settings.db.execute(sql=sql)

    @classmethod
    def setup_id_from_citation(
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
