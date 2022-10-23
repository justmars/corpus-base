from pydantic import BaseModel

from .settings import settings

vote_tbl = settings.tbl_decision_voteline


class VoteLine(BaseModel):
    """Each decision may contain a vote line, e.g. a summary of which justice voted for the main opinion and those who dissented, etc."""

    decision_id: str
    text: str

    @classmethod
    def make_table(cls):
        vote_tbl.create(
            columns={"id": int, "decision_id": str, "text": str},
            pk="id",
            foreign_keys=[("decision_id", settings.DecisionTableName, "id")],
            if_not_exists=True,
        )
        settings.add_indexes(vote_tbl, [["id", "decision_id"], ["text"]])
        settings.add_fts(vote_tbl, ["text"])
        return vote_tbl
