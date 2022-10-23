from citation_utils import Citation

from .settings import settings

cite_tbl = settings.tbl_decision_citation


class CitationRow(Citation):
    """Each Citation is associated with a decision."""

    decision_id: str

    @classmethod
    def make_table(cls):
        cite_tbl.create(
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
        settings.add_indexes(
            cite_tbl,
            [
                ["id", "decision_id"],
                ["docket_category", "docket_serial", "docket_date"],
                ["scra", "phil", "offg", "docket"],
                ["offg"],
                ["scra"],
                ["phil"],
                ["docket"],
            ],
        )
        return cite_tbl
