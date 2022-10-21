from typing import Iterator

from pydantic import BaseModel

from .settings import settings


class TitleTagRow(BaseModel):
    decision_id: str
    tag: str

    @classmethod
    def make_table(cls, db):
        tbl = db[settings.TitleTagTableName]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={"decision_id": str, "tag": str},
            pk="id",
            foreign_keys=[("decision_id", settings.DecisionTableName, "id")],
            if_not_exists=True,
        )
        return tbl

    @classmethod
    def extract_tags(cls, pk: str, text: str):
        for data in cls.set_tags_from_title(pk, text):
            yield cls(decision_id=pk, tag=data["tag"])

    @classmethod
    def insert_rows(cls, db, pk: str, text: str | None):
        if not text:
            return
        if items := cls.extract_tags(pk, text):
            tbl = cls.make_table(db)
            rows = [i.dict() for i in items]
            for row in rows:
                tbl.insert(row)

    @classmethod
    def set_tags_from_title(cls, pk: str, text: str) -> Iterator[dict]:
        def is_contained(target_text: str, matches: list[str]) -> bool:
            return any(m.lower() in target_text.lower() for m in matches)

        tags = []
        if is_contained(
            text,
            [
                "habeas corpus",
                "guardianship of",
                "writ of amparo",
                "habeas data",
                "change of name",
                "correction of entries",
                "escheat",
            ],
        ):
            tags.append("Special Proceeding")

        if is_contained(
            text,
            [
                "matter of the will",
                "testamentary proceedings",
                "probate",
            ],
        ):
            tags.append("Succession")

        if is_contained(
            text,
            [
                "disbarment",
                "practice of law",
                "office of the court administrator",
                "disciplinary action against atty.",
            ],
        ):
            tags.append("Legal Ethics")

        if is_contained(
            text,
            [
                "for naturalization",
                "certificate of naturalization",
                "petition for naturalization",
                "citizen of the philippines",
                "commissioner of immigration",
                "commissioners of immigration",
                "philippine citizenship",
            ],
        ):
            tags.append("Immigration")

        if is_contained(
            text,
            [
                "central bank of the philippines",
                "bangko sentral ng pilipinas",
            ],
        ):
            tags.append("Banking")

        if is_contained(
            text,
            [
                "el pueblo de filipinas",
                "el pueblo de las islas filipinas",
                "los estados unidos",
                "testamentaria",
            ],
        ):
            tags.append("Spanish")

        if is_contained(
            text,
            ["the united States, plaintiff "],
        ):
            tags.append("United States")

        if is_contained(
            text,
            [
                "people of the philipppines",
                "people of the philippines",
                "people  of the philippines",
                "people of the  philippines",
                "people of the philipines",
                "people of the philippine islands",
                "people philippines, of the",
                "sandiganbayan",
                "tanodbayan",
                "ombudsman",
            ],
        ):
            tags.append("Crime")

        if is_contained(
            text,
            [
                "director of lands",
                "land registration",
                "register of deeds",
            ],
        ):
            tags.append("Property")

        if is_contained(
            text,
            [
                "agrarian reform",
                "darab",
            ],
        ):
            tags.append("Agrarian Reform")

        if is_contained(
            text,
            [
                "collector of internal revenue",
                "commissioner of internal revenue",
                "bureau of internal revenue",
                "court of tax appeals",
            ],
        ):
            tags.append("Taxation")

        if is_contained(
            text,
            [
                "collector of customs",
                "commissioner of customs",
            ],
        ):
            tags.append("Customs")

        if is_contained(
            text,
            [
                "commission on elections",
                "comelec",
                "electoral tribunal",
            ],
        ):
            tags.append("Elections")

        if is_contained(
            text,
            [
                "workmen's compensation commission",
                "employees' compensation commission",
                "national labor relations commission",
                "bureau of labor relations",
                "nlrc",
                "labor union",
                "court of industrial relations",
            ],
        ):
            tags.append("Labor")

        for tag in tags:
            yield {"decision_id": pk, "tag": tag}
