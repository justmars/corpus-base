from pathlib import Path

from corpus_pax import Individual
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
from .utils import DECISION_PATH, extract_votelines, tags_from_title


def build_sc_tables(c: Connection) -> Connection:
    Justice.set_local_from_api()
    Justice.init_justices_tbl(c)
    c.create_table(DecisionRow)
    c.create_table(CitationRow)
    c.create_table(OpinionRow)
    c.create_table(VoteLine)
    c.create_table(TitleTagRow)
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
        return

    for email in obj.emails:  # assign author row to a joined m2m table
        case_tbl.update(decision_id).m2m(
            other_table=c.table(Individual), lookup={"email": email}, pk="id"
        )

    if obj.citation and obj.citation.has_citation:
        c.add_record(CitationRow, obj.citation_fk)  # add associated citation

    if obj.voting:  # process votelines of voting text in decision
        for item in extract_votelines(decision_id, obj.voting):
            c.add_record(VoteLine, item)

    if obj.title:  # add tags based on the title of decision
        for item in tags_from_title(decision_id, obj.title):
            c.add_record(TitleTagRow, item)

    justice_id = case_tbl.get(decision_id).get("justice_id")  # add opinions
    for op in OpinionRow.get_opinions(path.parent, decision_id, justice_id):
        c.add_record(OpinionRow, op.dict(exclude={"concurs", "tags"}))


def init_sc_cases(c: Connection, test_only: int = 0):
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for idx, details_file in enumerate(case_details):
        if test_only and idx == test_only:
            break
        try:
            setup_case(c, details_file)
        except Exception as e:
            logger.info(e)
