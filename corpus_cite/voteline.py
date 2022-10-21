from pydantic import BaseModel

from .settings import settings


class VoteLine(BaseModel):
    """Each decision may contain a vote line, e.g. a summary of which justice voted for the main opinion and those who dissented, etc."""

    decision_id: str
    text: str

    @classmethod
    def make_table(cls, db):
        tbl = db[settings.VotelineTableName]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={"id": int, "decision_id": str, "text": str},
            pk="id",
            foreign_keys=[("decision_id", settings.DecisionTableName, "id")],
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
    def insert_rows(cls, db, pk: str, text: str | None):
        if not text:
            return
        if items := cls.extract_lines(pk, text):
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
