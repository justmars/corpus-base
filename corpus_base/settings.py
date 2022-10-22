import re
import sys
from pathlib import Path
from typing import Iterator

import httpx
from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger
from pydantic import BaseSettings, Field
from sqlite_utils import Database


class BaseCaseSettings(BaseSettings):
    DecisionSourceFiles: str = Field(
        "code/corpus/decisions",
        env="DecisionSourceFiles",
        description="String that represents the path to the decisions.",
    )
    DatabasePath: str = Field(
        ...,
        env="DB_FILE",
        description="Intended / existing path to the database.",
    )

    GithubToken: str = Field(..., repr=False, env="EXPIRING_TOKEN")
    GithubOwner: str = Field("justmars", env="OWNER")
    GithubRepo: str = Field("corpus", env="REPOSITORY")

    JusticeTableName: str = Field("justices_tbl")
    DecisionTableName: str = Field("decisions_tbl")
    CitationTableName: str = Field("decision_citations_tbl")
    VotelineTableName: str = Field("decision_votelines_tbl")
    TitleTagTableName: str = Field("decision_titletags_tbl")

    @property
    def db(self) -> Database:
        return Database(
            Path().home().joinpath(self.DatabasePath),
            use_counts_table=True,
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def call_api(self) -> httpx.Response | None:
        if all([self.GithubToken, self.GithubOwner, self.GithubRepo]):
            with httpx.Client() as client:
                return client.get(
                    f"https://api.github.com/repos/{self.GithubOwner}/{self.GithubRepo}/contents/justices/sc.yaml",
                    headers=dict(
                        Authorization=f"token {self.GithubToken}",
                        Accept="application/vnd.github.VERSION.raw",
                    ),
                )
        return None

    @property
    def local_justice_file(self) -> Path:
        """Location of the justice file created"""
        return Path(__file__).parent / "sc.yaml"

    @property
    def case_folders(self) -> Iterator[Path]:
        """Details.yaml files to be used for creation of decision rows and other components."""
        return (
            Path()
            .home()
            .joinpath(self.DecisionSourceFiles)
            .glob("**/*/details.yaml")
        )

    @property
    def base_env(self):
        """The Jinja2 environment to yield various sql files."""
        return Environment(
            loader=PackageLoader(
                package_name="corpus_base", package_path="templates"
            ),
            autoescape=select_autoescape(),
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
MAX_JUSTICE_AGE = 70

## VIEWS
CHIEF_DATES_VIEW = "chief_dates"

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
