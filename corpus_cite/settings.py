import re
import sys
from pathlib import Path
from typing import Iterator

from loguru import logger
from pydantic import BaseSettings, Field
from sqlite_utils import Database


class BaseCaseSettings(BaseSettings):
    DecisionSourceFiles: str = Field(
        ...,
        env="DecisionSourceFiles",
        description="String that represents the path to the decisions.",
    )
    DatabasePath: str = Field(
        ...,
        env="DB_FILE",
        description="Intended / existing path to the database.",
    )
    DecisionTableName: str = Field("decisions_tbl")
    CitationTableName: str = Field("decision_citations_tbl")
    VotelineTableName: str = Field("decision_votelines_tbl")
    TitleTagTableName: str = Field("decision_titletags_tbl")

    @property
    def db(self) -> Database:
        return Database(
            Path().home().joinpath(self.DatabasePath), use_counts_table=True
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def case_folders(self) -> Iterator[Path]:
        return (
            Path()
            .home()
            .joinpath(self.DecisionSourceFiles)
            .glob("**/*/details.yaml")
        )


settings = BaseCaseSettings()  # pyright: ignore


CATEGORY_START_DECISION = re.compile(r"d\s*e\s*c", re.I)
CATEGORY_START_RESOLUTION = re.compile(r"r\s*e\s*s", re.I)
COMPOSITION_START_DIVISION = re.compile(r"div", re.I)
COMPOSITION_START_ENBANC = re.compile(r"en", re.I)


## Numbers

VOTEFULL_MIN_LENGTH = 20
VOTELINE_MIN_LENGTH = 15
VOTELINE_MAX_LENGTH = 1000


## Logger

logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "{message}",
            "level": "ERROR",
        },
        {
            "sink": "logs/decision.log",
            "format": "{message}",
            "level": "WARNING",
            "serialize": True,
        },
    ]
)
