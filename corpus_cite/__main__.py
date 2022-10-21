from pathlib import Path

from loguru import logger

from .citation import CitationRow
from .decision import DecisionRow
from .settings import BaseCaseSettings
from .titletags import TitleTagRow
from .voteline import VoteLine


def setup_base_case_tbls(db):
    DecisionRow.make_table(db)
    CitationRow.make_table(db)
    VoteLine.make_table(db)
    TitleTagRow.make_table(db)
    return db


def add_base_case_components(db, path: Path):
    obj = DecisionRow.from_path(path)
    cite = obj.citation.dict()
    DecisionRow.insert_row(db, obj.dict())
    CitationRow.insert_row(db, {"decision_id": obj.id} | cite)
    VoteLine.insert_rows(db, obj.id, obj.voting)
    TitleTagRow.insert_rows(db, obj.id, obj.title)


def add_cases(settings: BaseCaseSettings):
    for details_file in settings.case_folders:
        try:
            add_base_case_components(settings.db, details_file)
        except Exception as e:
            logger.info(e)
