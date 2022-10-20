from typing import Iterator

from pydantic import BaseModel

from .resources import DECISION_TBL, VOTELINE_TBL


class VoteLine(BaseModel):
    """Each decision may contain a vote line, e.g. a summary of which justice voted for the main opinion and those who dissented, etc."""

    decision_id: str
    text: str

    @classmethod
    def make_table(cls, db):
        tbl = db[VOTELINE_TBL]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={"id": int, "decision_id": str, "text": str},
            pk="id",
            foreign_keys=[("decision_id", DECISION_TBL, "id")],
            if_not_exists=True,
        )
        idx_prefix = "idx_votes_"
        indexes = [["id", "decision_id"]]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        tbl.enable_fts(
            ["text"],
            create_triggers=True,
            replace=True,
            tokenize="porter",
        )
        return tbl

    @classmethod
    def insert_rows(cls, db, items: Iterator["VoteLine"]):
        if items:
            tbl = cls.make_table(db)
            rows = [i.dict() for i in items]
            for row in rows:
                tbl.insert(row)

    @classmethod
    def extract_lines(cls, pk: str, text: str):
        from .helpers import is_line_ok

        for line in text.splitlines():
            if is_line_ok(line):
                yield cls(decision_id=pk, text=line)
