import re
from collections.abc import Iterator

from pydantic import Field
from sqlpyd import TableConfig

from .decision import DecisionRow, OpinionRow

single_spaced = re.compile(r"\s*\n\s*")
double_spaced = re.compile(r"\s*\n\s*\n\s*")


def standardize(text: str):
    return (
        text.removeprefix("# Ponencia")
        .replace("\xa0", "")
        .replace("\xad", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .strip()
    )


class SegmentRow(TableConfig):
    __prefix__ = "sc"
    __tablename__ = "segments"
    __indexes__ = [
        ["opinion_id", "decision_id"],
    ]
    id: str = Field(..., col=str)
    decision_id: str = Field(
        ...,
        col=str,
        fk=(DecisionRow.__tablename__, "id"),
    )
    opinion_id: str = Field(
        ...,
        col=str,
        fk=(OpinionRow.__tablename__, "id"),
    )
    position: str = Field(
        ...,
        title="Relative Position",
        description="The line number of the text as stripped from its markdown source.",
        col=int,
        index=True,
    )
    char_count: int = Field(
        ...,
        title="Character Count",
        description="The number of characters of the text makes it easier to discover patterns.",
        col=int,
        index=True,
    )
    segment: str = Field(
        ...,
        title="Body Segment",
        description="A partial text fragment of an opinion, exclusive of footnotes.",
        col=str,
        fts=True,
    )

    @classmethod
    def segmentize(cls, full_text: str) -> Iterator[dict]:
        """Split first by double-spaced breaks `\n\n` and then by
        single spaced breaks `\n` to get the position of the segment.

        Will exclude footnotes and segments with less than 10 characters

        Args:
            full_text (str): The opinion to segment

        Yields:
            Iterator[dict]: The partial segment data fields
        """
        if cleaned_text := standardize(full_text):
            if subdivisions := double_spaced.split(cleaned_text):
                for idx, text in enumerate(subdivisions):
                    if lines := single_spaced.split(text):
                        for sub_idx, segment in enumerate(lines):
                            # --- marks the footnote boundary
                            if segment == "---":
                                return
                            position = f"{idx}-{sub_idx}"
                            char_count = len(segment)
                            if char_count > 10:
                                yield {
                                    "position": position,
                                    "segment": segment,
                                    "char_count": char_count,
                                }
