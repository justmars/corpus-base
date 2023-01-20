from pathlib import Path

from corpus_pax import Individual, setup_pax
from corpus_pax.utils import delete_tables_with_prefix
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
from .segment import SegmentRow
from .utils import DECISION_PATH, extract_votelines, tags_from_title


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
    """Parse a case's `details.yaml` found in the `path`
    to generate rows for various `sc_tbl` prefixed sqlite tables found.

    After creation a decision row, get correlated metadata involving
    the decision: the citation, voting text, tags from the title, etc.,
    and then add rows for their respective tables.

    Args:
        c (Connection): sqlpyd Connection
        path (Path): path to a case's details.yaml
    """

    # initialize content from the path
    case_tbl = c.table(DecisionRow)
    obj = DecisionRow.from_path(c, path)

    try:
        decision_id = case_tbl.insert(obj.dict(), pk="id").last_pk  # type: ignore
        logger.debug(f"Added {decision_id=}")
    except Exception as e:
        logger.error(f"Skipping duplicate {obj=}; {e=}")
        return
    if not decision_id:
        logger.error(f"Could not find decision_id for {obj=}")
        return

    # assign author row to a joined m2m table, note the explicit m2m table name
    # so that the prefix used is `sc`; the default will start with `pax_`
    for email in obj.emails:
        case_tbl.update(decision_id).m2m(
            other_table=c.table(Individual),
            pk="id",
            lookup={"email": email},
            m2m_table="sc_tbl_decisions_pax_tbl_individuals",
        )

    # add associated citation
    if obj.citation and obj.citation.has_citation:
        c.add_record(CitationRow, obj.citation_fk)

    # process votelines of voting text in decision
    if obj.voting:
        c.add_records(VoteLine, extract_votelines(decision_id, obj.voting))

    # add tags based on the title of decision
    if obj.title:
        c.add_records(TitleTagRow, tags_from_title(decision_id, obj.title))

    # add opinions and segments
    for op in OpinionRow.get_opinions(
        case_path=path.parent,
        decision_id=decision_id,
        justice_id=case_tbl.get(decision_id).get("justice_id"),
    ):
        c.add_record(OpinionRow, op.dict(exclude={"concurs", "tags"}))
        c.add_records(SegmentRow, op.segments)


def init_sc_cases(c: Connection, test_only: int = 0):
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for idx, details_file in enumerate(case_details):
        if test_only and idx == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)


def add_authors_only(c: Connection):
    """Helper function for just adding the author decision m2m table."""
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for detail_path in case_details:
        obj = DecisionRow.from_path(c, detail_path)
        for email in obj.emails:  # assign author row to a joined m2m table
            tbl = c.table(DecisionRow)
            if tbl.get(obj.id):
                tbl.update(obj.id).m2m(
                    other_table=c.table(Individual),
                    lookup={"email": email},
                    pk="id",
                    m2m_table="sc_tbl_decisions_pax_tbl_individuals",
                )


def setup_base(db_path: str, test_num: int | None = None) -> Connection:
    """Recreates tables and populates the same.

    Since there are thousands of cases, limit the number of downloads
    via the `test_num`.

    Args:
        db_path (str): string path from the cwd
        test_num (int | None, optional): e.g. how many cases will it
            add to the database. Defaults to None.

    Returns:
        Connection: sqlpyd wrapper sqlite.utils Database
    """
    c = Connection(DatabasePath=db_path, WAL=True)  # type: ignore
    delete_tables_with_prefix(c, ["sc"])
    build_sc_tables(c)
    if test_num:
        init_sc_cases(c, test_num)
    else:
        init_sc_cases(c)
    return c


def setup_pax_base(db_path: str):
    setup_pax(db_path)
    setup_base(db_path)
