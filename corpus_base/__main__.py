from pathlib import Path

from corpus_persons import Individual
from loguru import logger
from sqlpyd import Connection

from .decision import (
    CitationRow,
    DecisionRow,
    OpinionRow,
    TitleTagRow,
    VoteLine,
)
from .justice import Justice
from .utils import CASE_FOLDERS, extract_votelines, tags_from_title


def create_if_not_exist(kls, c: Connection):
    tbl = c.tbl(kls.__tablename__)
    if not tbl.exists():
        kls.make_table(c)
        return None


def build_sc_tables(c: Connection) -> None:
    Justice.set_local_from_api()
    Justice.init_justices_tbl(c)
    create_if_not_exist(DecisionRow, c)
    create_if_not_exist(CitationRow, c)
    create_if_not_exist(OpinionRow, c)
    create_if_not_exist(VoteLine, c)
    create_if_not_exist(TitleTagRow, c)
    c.db.index_foreign_keys()


def setup_case(c: Connection, path: Path) -> None:
    """
    1. Adds a decision row
    2. Updates the decision row's justice id
    3. Adds a citation row
    4. Adds voteline rows
    5. Adds opinion rows
    """
    case_tbl = c.tbl(DecisionRow.__tablename__)
    cite_tbl = c.tbl(CitationRow.__tablename__)
    opin_tbl = c.tbl(OpinionRow.__tablename__)
    vote_tbl = c.tbl(VoteLine.__tablename__)
    tags_tbl = c.tbl(TitleTagRow.__tablename__)
    authors_tbl = c.tbl(Individual.__tablename__)

    obj = DecisionRow.from_path(c, path)

    try:  # add decision row
        decision_id = case_tbl.insert(obj.dict(), pk="id").last_pk  # type: ignore
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        return

    for email in obj.emails:  # assign an author row to a joined m2m table
        case_tbl.update(obj.id).m2m(
            other_table=authors_tbl, lookup={"email": email}, pk="id"
        )

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
    for op in OpinionRow.get_opinions(path.parent, justice_id):
        opin_tbl.insert(op.dict(exclude={"concurs", "tags"}))


def init_sc_cases(c: Connection, test_only: int = 0):
    for counter, details_file in enumerate(CASE_FOLDERS):
        if test_only and counter == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)
