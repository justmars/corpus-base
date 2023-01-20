from sqlpyd import Connection

from corpus_base import (
    CitationRow,
    DecisionRow,
    Justice,
    OpinionRow,
    TitleTagRow,
    VoteLine,
)


def test_rows_made(session: Connection):
    assert session.table(Justice).count == 194
    assert session.table(DecisionRow).count == 3
    assert session.table(CitationRow).count == 3
    assert session.table(OpinionRow).count == 3
    assert session.table(TitleTagRow).count == 2
    assert session.table(VoteLine).count == 10
    assert len(session.db.table_names()) == 47
