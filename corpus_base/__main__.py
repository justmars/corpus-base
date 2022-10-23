from pathlib import Path

from loguru import logger

from .citation import CitationRow
from .decision import DecisionRow
from .justice import Justice
from .opinions import OpinionRow
from .settings import settings
from .titletags import TitleTagRow
from .utils import extract_votelines, tags_from_title
from .voteline import VoteLine

db = settings.db


def setup_base_tbls():
    Justice.make_table()
    DecisionRow.make_table()
    OpinionRow.make_table()
    CitationRow.make_table()
    VoteLine.make_table()
    TitleTagRow.make_table()
    db.index_foreign_keys()
    return db


def setup_case(path: Path):
    """
    1. Adds a decision row
    2. Updates the decision row's justice id
    3. Adds a citation row
    4. Adds voteline rows
    5. Adds opinion rows
    """
    obj = DecisionRow.from_path(path)

    # add decision row
    try:
        decision_id = settings.tbl_decision.insert(obj.dict(), pk="id").last_pk  # type: ignore
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        return

    # add associated citation of decision
    if obj.citation.has_citation:
        settings.tbl_decision_citation.insert(
            CitationRow(**obj.citation_fk).dict()
        )

    # process votelines of voting text in decision
    if obj.voting:
        for item in extract_votelines(decision_id, obj.voting):
            settings.tbl_decision_voteline.insert(VoteLine(**item).dict())

    # add tags based on the title of decision
    if obj.title:
        for item in tags_from_title(decision_id, obj.title):
            settings.tbl_decision_titletags.insert(TitleTagRow(**item).dict())

    # add opinions
    justice_id = settings.tbl_decision.get(decision_id).get("justice_id")
    for opinion in OpinionRow.get_opinions(path.parent, justice_id):
        settings.tbl_opinion.insert(opinion.dict(exclude={"concurs", "tags"}))


def init(test_only: int = 0):
    # create tables
    setup_base_tbls()

    # insert justices into the justice table
    Justice.from_api()
    Justice.init_justices_tbl()

    # infuse decision tables from path
    for counter, details_file in enumerate(settings.case_folders):
        if test_only and counter == test_only:
            break
        try:
            setup_case(details_file)
        except Exception as e:
            logger.info(e)
