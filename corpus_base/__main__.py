from pathlib import Path

from loguru import logger
from sqlite_utils import Database

from .citation import CitationRow
from .decision import DecisionRow
from .justice import Justice
from .settings import settings
from .titletags import TitleTagRow
from .voteline import VoteLine


def setup_base_tbls(db: Database):
    Justice.make_table(db)
    DecisionRow.make_table(db)
    CitationRow.make_table(db)
    VoteLine.make_table(db)
    TitleTagRow.make_table(db)
    db.index_foreign_keys()
    return db


def add_base_case_components(db, path: Path):
    obj = DecisionRow.from_path(path)
    cite = obj.citation.dict()
    DecisionRow.insert_row(db, obj.dict())
    CitationRow.insert_row(db, {"decision_id": obj.id} | cite)
    VoteLine.insert_rows(db, obj.id, obj.voting)
    TitleTagRow.insert_rows(db, obj.id, obj.title)


def init(test_only: int = 0):
    # create tables
    setup_base_tbls(settings.db)

    # insert justices into the justice table
    Justice.from_api()
    Justice.init_justices_tbl()

    # infuse decision tables from path

    for idx, details_file in enumerate(settings.case_folders):
        if test_only:
            if idx == test_only:
                break
        try:
            add_base_case_components(settings.db, details_file)
        except Exception as e:
            logger.info(e)

    # update justice id column in the decisions table
    settings.db.execute(
        sql=settings.base_env.get_template("update_justice_ids.sql").render(
            justice_table=settings.JusticeTableName,
            decision_table=settings.DecisionTableName,
        ),
    )
