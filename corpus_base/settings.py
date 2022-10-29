import sys
from pathlib import Path
from typing import Iterator

from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger
from pydantic import BaseSettings, Field
from sqlite_utils import Database


class BaseCaseSettings(BaseSettings):
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
