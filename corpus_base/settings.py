import sys
from pathlib import Path
from typing import Iterator

import httpx
from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger
from pydantic import BaseSettings, Field
from sqlite_utils import Database
from sqlpyd import Connection


class JusticeParts(BaseSettings):
    GithubToken: str = Field(..., repr=False, env="EXPIRING_TOKEN")
    GithubOwner: str = Field("justmars", env="OWNER")
    GithubRepo: str = Field("corpus", env="REPOSITORY")

    JusticeTableName: str = Field("justices_tbl")


class BaseCaseSettings(JusticeParts):
    DatabasePath: str = Field(
        ...,
        env="DB_FILE",
        description="Intended / existing path to the database.",
    )
    DecisionSourceFiles: str = Field(
        "code/corpus/decisions",
        env="DecisionSourceFiles",
        description="String that represents the path to the decisions.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def db(self) -> Database:
        obj = Database(
            Path().home().joinpath(self.DatabasePath),
            use_counts_table=True,
        )
        obj.enable_wal()
        return obj

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
    def sc_env(self):
        """The Jinja2 environment to yield various sql files."""
        return Environment(
            loader=PackageLoader(
                package_name="corpus_base", package_path="templates"
            ),
            autoescape=select_autoescape(),
        )


conn = Connection()  # pyright: ignore
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
