from pathlib import Path

from loguru import logger
from sqlite_utils import Database
from sqlpyd import Connection

from .decision import CitationRow, DecisionRow, TitleTagRow, VoteLine
from .justice import Justice
from .opinions import OpinionRow
from .settings import settings
from .utils import extract_votelines, tags_from_title


def setup_base_tbls(c: Connection) -> None:
    Justice.make_table(c)
    DecisionRow.make_table(c)
    OpinionRow.make_table(c)
    CitationRow.make_table(c)
    VoteLine.make_table(c)
    TitleTagRow.make_table(c)
    c.db.index_foreign_keys()


def setup_case(c: Connection, path: Path) -> None:
    """
    1. Adds a decision row
    2. Updates the decision row's justice id
    3. Adds a citation row
    4. Adds voteline rows
    5. Adds opinion rows
    """
    obj = DecisionRow.from_path(c, path)
    case_tbl = c.tbl(DecisionRow.__tablename__)
    cite_tbl = c.tbl(CitationRow.__tablename__)
    opin_tbl = c.tbl(OpinionRow.__tablename__)
    vote_tbl = c.tbl(VoteLine.__tablename__)
    tags_tbl = c.tbl(TitleTagRow.__tablename__)

    # add decision row
    try:
        decision_id = case_tbl.insert(obj.dict(), pk="id").last_pk  # type: ignore
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        return

    # add associated citation of decision
    if obj.citation and obj.citation.has_citation:
        cite_tbl.insert(CitationRow(**obj.citation_fk).dict())

    # process votelines of voting text in decision
    if obj.voting:
        for item in extract_votelines(decision_id, obj.voting):
            vote_tbl.insert(VoteLine(**item).dict())

    # add tags based on the title of decision
    if obj.title:
        for item in tags_from_title(decision_id, obj.title):
            tags_tbl.insert(TitleTagRow(**item).dict())

    # add opinions
    justice_id = case_tbl.get(decision_id).get("justice_id")
    for opinion in OpinionRow.get_opinions(path.parent, justice_id):
        opin_tbl.insert(opinion.dict(exclude={"concurs", "tags"}))


def init(c: Connection, test_only: int = 0):
    # create tables
    setup_base_tbls(c)

    # insert justices into the justice table
    Justice.from_api()
    Justice.init_justices_tbl(c)

    # infuse decision tables from path
    for counter, details_file in enumerate(settings.case_folders):
        if test_only and counter == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)
