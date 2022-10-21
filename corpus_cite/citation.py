from citation_utils import Citation

from .settings import settings


class CitationRow(Citation):
    """Each Citation is associated with a decision."""

    decision_id: str

    @classmethod
    def make_table(cls, db):
        tbl = db[settings.CitationTableName]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={
                "id": int,
                "decision_id": str,
                "scra": str,
                "phil": str,
                "offg": str,
                "docket": str,
                "docket_category": str,
                "docket_serial": str,
                "docket_date": str,
            },
            pk="id",
            foreign_keys=[("decision_id", settings.DecisionTableName, "id")],
            if_not_exists=True,
        )
        idx_prefix = "idx_cites_"
        indexes = [
            ["id", "decision_id"],
            ["docket_category", "docket_serial", "docket_date"],
            ["scra", "phil", "offg", "docket"],
            ["offg"],
            ["scra"],
            ["phil"],
            ["docket"],
        ]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        return tbl

    @classmethod
    def insert_row(cls, db, item: dict):
        tbl = cls.make_table(db)
        tbl.insert(item)
