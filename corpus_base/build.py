from pathlib import Path

import yaml
from corpus_pax import Individual, setup_pax
from corpus_pax.utils import delete_tables_with_prefix
from corpus_sc_toolkit import (
    DECISION_PATH,
    InterimDecision,
    Justice,
    extract_votelines,
    get_justices_file,
    tags_from_title,
)
from loguru import logger
from sqlite_utils.db import Database
from sqlpyd import Connection

from .main import (
    CitationRow,
    DecisionRow,
    OpinionRow,
    SegmentRow,
    TitleTagRow,
    VoteLine,
)


def build_sc_tables(c: Connection) -> Connection:
    c.add_records(Justice, yaml.safe_load(get_justices_file().read_bytes()))
    c.create_table(DecisionRow)
    c.create_table(CitationRow)
    c.create_table(OpinionRow)
    c.create_table(VoteLine)
    c.create_table(TitleTagRow)
    c.create_table(SegmentRow)
    c.db.index_foreign_keys()
    return c


def add_decision_meta(c: Connection, decision: DecisionRow) -> str | None:
    """This creates a decision row and correlated metadata involving
    the decision, i.e. the citation, voting text, tags from the title, etc.,
    and then add rows for their respective tables.

    Args:
        c (Connection): sqlpyd wrapper over sqlite_utils
        decision (DecisionRow): Uniform fields ready for database insertion

    Returns:
        str | None: The decision id, if the insertion of records is successful.
    """
    case_tbl = c.table(DecisionRow)
    try:
        decision_id = case_tbl.insert(decision.dict(), pk="id").last_pk  # type: ignore
        logger.debug(f"Added {decision_id=}")
    except Exception as e:
        logger.error(f"Skipping duplicate {decision=}; {e=}")
        return None
    if not decision_id:
        logger.error(f"Could not find decision_id for {decision=}")
        return None

    # assign author row to a joined m2m table, note the explicit m2m table name
    # so that the prefix used is `sc`; the default will start with `pax_`
    for email in decision.emails:
        case_tbl.update(decision_id).m2m(
            other_table=c.table(Individual),
            pk="id",
            lookup={"email": email},
            m2m_table="sc_tbl_decisions_pax_tbl_individuals",
        )

    # add associated citation
    if decision.citation and decision.citation.has_citation:
        c.add_record(
            kls=CitationRow,
            item=decision.citation_fk,
        )

    # process votelines of voting text in decision
    if decision.voting:
        c.add_records(
            VoteLine,
            extract_votelines(
                decision_pk=decision_id,
                text=decision.voting,
            ),
        )

    # add tags based on title of decision
    if decision.title:
        c.add_records(
            TitleTagRow,
            tags_from_title(
                decision_pk=decision_id,
                text=decision.title,
            ),
        )
    return decision.id


def setup_decision_from_pdf(c: Connection, pdf_obj: InterimDecision) -> None:
    """Transfer pre-processed `pdf_obj`, per corpus-sc-toolkit.
    to generate rows for various `sc_tbl` prefixed sqlite tables found.

    Args:
        c (Connection): sqlpyd wrapper over sqlite_utils
        pdf_obj (InterimDecision): see corpus-sc-toolkit
    """
    obj = DecisionRow.from_pdf(pdf_obj)
    if not obj:
        logger.error(f"Skipping bad {pdf_obj.id=}; {pdf_obj.origin=}")
        return
    decision_id = add_decision_meta(c, obj)
    if not decision_id:
        logger.error(f"Could not setup pdf-based {obj.id=}; {obj.origin=}")
        return
    for op in pdf_obj.opinions:
        c.add_record(OpinionRow, op.row)
        for segment in op.segments:
            c.add_record(SegmentRow, segment._asdict())


def setup_decision_from_path(c: Connection, path: Path) -> None:
    """Parse a case's `details.yaml` found in the `path`
    to generate rows for various `sc_tbl` prefixed sqlite tables found.

    Args:
        c (Connection): sqlpyd wrapper over sqlite_utils
        path (Path): path to a case's details.yaml
    """
    obj = DecisionRow.from_path(c, path)
    if not obj:
        logger.error(f"Skipping bad {path=}")
        return
    decision_id = add_decision_meta(c, obj)
    if not decision_id:
        logger.error(f"Could not setup path-based {obj.id=}; {path=}")
        return
    for op in OpinionRow.get_opinions(
        case_path=path.parent,
        decision_id=decision_id,
        justice_id=c.table(DecisionRow).get(decision_id).get("justice_id"),
    ):
        c.add_record(OpinionRow, op.dict(exclude={"concurs", "tags"}))
        c.add_records(SegmentRow, op.segments)


def add_authors_only(c: Connection):
    """Helper function for just adding the author decision m2m table."""
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for detail_path in case_details:
        if obj := DecisionRow.from_path(c, detail_path):
            for email in obj.emails:  # assign author row to a joined m2m table
                tbl = c.table(DecisionRow)
                if tbl.get(obj.id):
                    tbl.update(obj.id).m2m(
                        other_table=c.table(Individual),
                        lookup={"email": email},
                        pk="id",
                        m2m_table="sc_tbl_decisions_pax_tbl_individuals",
                    )


def add_cases_from_path(c: Connection, test_only: int = 0) -> Database:
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for idx, details_file in enumerate(case_details):
        if test_only and idx == test_only:
            break
        try:
            setup_decision_from_path(c, details_file)
        except Exception as e:
            logger.info(e)
    return c.db


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
        add_cases_from_path(c, test_num)
    else:
        add_cases_from_path(c)
    return c


def setup_pax_base(db_path: str, test_num: int | None = None) -> Connection:
    setup_pax(db_path)
    return setup_base(db_path, test_num)
