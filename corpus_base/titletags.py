from pydantic import BaseModel

from .settings import settings


class TitleTagRow(BaseModel):
    decision_id: str
    tag: str

    @classmethod
    def make_table(cls):
        return settings.tbl_decision_titletags.create(
            columns={"decision_id": str, "tag": str},
            pk="id",
            foreign_keys=[("decision_id", settings.DecisionTableName, "id")],
            if_not_exists=True,
        )
