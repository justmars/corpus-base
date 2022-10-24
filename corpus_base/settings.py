import sys
from pathlib import Path
from typing import Iterator

import httpx
from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger
from pydantic import BaseSettings, Field
from sqlite_utils import Database
from sqlite_utils.db import Table


class JusticeParts(BaseSettings):
    GithubToken: str = Field(..., repr=False, env="EXPIRING_TOKEN")
    GithubOwner: str = Field("justmars", env="OWNER")
    GithubRepo: str = Field("corpus", env="REPOSITORY")

    JusticeTableName: str = Field("justices_tbl")


class DecisionParts(BaseSettings):
    DecisionSourceFiles: str = Field(
        "code/corpus/decisions",
        env="DecisionSourceFiles",
        description="String that represents the path to the decisions.",
    )
    CitationTableName: str = Field("decision_citations_tbl")
    VotelineTableName: str = Field("decision_votelines_tbl")
    TitleTagTableName: str = Field("decision_titletags_tbl")


class BaseCaseSettings(DecisionParts, JusticeParts):
    DatabasePath: str = Field(
        ...,
        env="DB_FILE",
        description="Intended / existing path to the database.",
    )
    DecisionTableName: str = Field("decisions_tbl")
    OpinionTableName: str = Field("opinions_tbl")

    @property
    def db(self) -> Database:
        obj = Database(
            Path().home().joinpath(self.DatabasePath),
            use_counts_table=True,
        )
        obj.enable_wal()
        return obj

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

    def set_table(self, table_name: str) -> Table:
        tbl = self.db[table_name]
        if isinstance(tbl, Table):
            return tbl
        raise Exception(f"Missing {table_name=}")

    @property
    def tbl_justice(self) -> Table:
        return self.set_table(self.JusticeTableName)

    @property
    def tbl_decision(self) -> Table:
        return self.set_table(self.DecisionTableName)

    @property
    def tbl_decision_citation(self) -> Table:
        return self.set_table(self.CitationTableName)

    @property
    def tbl_decision_voteline(self) -> Table:
        return self.set_table(self.VotelineTableName)

    @property
    def tbl_decision_titletags(self) -> Table:
        return self.set_table(self.TitleTagTableName)

    @property
    def tbl_opinion(self) -> Table:
        return self.set_table(self.OpinionTableName)

    @classmethod
    def add_indexes(cls, tbl: Table, indexes: list[list[str]]):
        for i in indexes:
            idx_name = "_".join(["idx", tbl.name, "_".join(i)])
            tbl.create_index(i, idx_name, if_not_exists=True)

    @classmethod
    def add_fts(cls, tbl: Table, columns: list[str]):
        tbl.enable_fts(
            columns=columns,
            create_triggers=True,
            replace=True,
            tokenize="porter",
        )


settings = BaseCaseSettings()  # pyright: ignore


## Logger

logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "{message}",
            "level": "ERROR",
        },
        {
            "sink": "logs/base.log",
            "format": "{message}",
            "level": "WARNING",
            "serialize": True,
        },
    ]
)
