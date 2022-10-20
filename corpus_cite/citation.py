from citation_utils import Citation

from .resources import CITATION_TBL, DECISION_TBL


class CitationRow(Citation):
    """Each Citation is associated with a decision."""

    decision_id: str

    @classmethod
    def make_table(cls, db):
        tbl = db[CITATION_TBL]
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
            foreign_keys=[("decision_id", DECISION_TBL, "id")],
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
