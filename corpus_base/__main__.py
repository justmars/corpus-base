from pathlib import Path

from corpus_pax import Individual, setup_pax
from loguru import logger
from sqlpyd import Connection

from .decision import (
    CitationRow,
    DecisionRow,
    OpinionRow,
    SegmentRow,
    TitleTagRow,
    VoteLine,
)
from .justice import Justice
from .utils import DECISION_PATH, extract_votelines, tags_from_title

TABLE_LIST = [
    # delete m2m tables
    "pax_tbl_individuals_sc_tbl_decisions",
    # delete all segment related tables
    "sc_tbl_segments",
    "sc_tbl_segments_fts",
    # delete all decision add on tables
    "sc_tbl_titletags",
    "sc_tbl_votelines",
    "sc_tbl_citations",
    # delete all opinion related tables
    "sc_tbl_opinions",
    "sc_tbl_opinions_fts",
    # delete all article related tables
    "pax_tbl_articles_pax_tbl_individuals",
    "pax_tbl_articles_pax_tbl_tags",
    "pax_tbl_articles",
    # finally, delete the individual table
]


def build_sc_tables(c: Connection) -> Connection:
    Justice.set_local_from_api()
    Justice.init_justices_tbl(c)
    c.create_table(DecisionRow)
    c.create_table(CitationRow)
    c.create_table(OpinionRow)
    c.create_table(VoteLine)
    c.create_table(TitleTagRow)
    c.create_table(SegmentRow)
    c.db.index_foreign_keys()
    return c


def setup_case(c: Connection, path: Path) -> None:
    case_tbl = c.table(DecisionRow)
    obj = DecisionRow.from_path(c, path)

    try:  # add decision row
        decision_id = case_tbl.insert(obj.dict(), pk="id").last_pk  # type: ignore
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        logger.error(f"Could not find decision_id for {obj=}")
        return

    for email in obj.emails:  # assign author row to a joined m2m table
        case_tbl.update(decision_id).m2m(
            other_table=c.table(Individual), lookup={"email": email}, pk="id"
        )

    if obj.citation and obj.citation.has_citation:
        c.add_record(CitationRow, obj.citation_fk)  # add associated citation

    if obj.voting:  # process votelines of voting text in decision
        c.add_records(VoteLine, extract_votelines(decision_id, obj.voting))

    if obj.title:  # add tags based on the title of decision
        c.add_records(TitleTagRow, tags_from_title(decision_id, obj.title))

    # add opinions
    for op in OpinionRow.get_opinions(
        case_path=path.parent,
        decision_id=decision_id,
        justice_id=case_tbl.get(decision_id).get("justice_id"),
    ):
        c.add_record(OpinionRow, op.dict(exclude={"concurs", "tags"}))
        c.add_records(SegmentRow, op.segments)  # add segments


def init_sc_cases(c: Connection, test_only: int = 0):
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for idx, details_file in enumerate(case_details):
        if test_only and idx == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)


def setup_base(db_path: str, test_num: int | None = None) -> Connection:
    """Recreates tables and populates the same.

    Since there are thousands of cases, can limit the number of downloads
    via the `test_num`.

    Args:
        db_path (str): string path from the cwd
        test_num (int | None, optional): e.g. how many cases will it
            add to the database. Defaults to None.

    Returns:
        Connection: sqlpyd wrapper sqlite.utils Database
    """
    c = Connection(DatabasePath=db_path, WAL=True)  # type: ignore
    for tbl in TABLE_LIST:
        c.db.execute(f"drop table if exists {tbl}")
    build_sc_tables(c)
    if test_num:
        init_sc_cases(c, test_num)
    else:
        init_sc_cases(c)
    return c


def setup_pax_base(db_path: str):
    setup_pax(db_path)
    setup_base(db_path)
