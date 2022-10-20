from pathlib import Path

from .citation import CitationRow
from .decision import DecisionRow
from .titletags import TitleTagRow
from .voteline import VoteLine


def setup(db):
    DecisionRow.make_table(db)
    CitationRow.make_table(db)
    VoteLine.make_table(db)
    TitleTagRow.make_table(db)


def add_components(db, path: Path):
    obj = DecisionRow.from_path(path)
    cite = obj.citation.dict() | {"decision_id": obj.id}
    DecisionRow.insert_row(db, obj.dict())
    CitationRow.insert_row(db, cite)
    if obj.voting:
        VoteLine.insert_rows(db, VoteLine.extract_lines(obj.id, obj.voting))
    if tags := TitleTagRow.extract_tags(obj.id, obj.title):
        TitleTagRow.insert_rows(db, tags)


def add_cases(db, paths):
    for i in paths:
        try:
            add_components(db, i)
        except Exception:
            continue
