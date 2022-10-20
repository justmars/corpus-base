import os
import re
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from loguru import logger
from sqlite_utils import Database

load_dotenv(find_dotenv())

SRC_FILES = os.getenv("SRC_FILES", "code/corpus/decisions/**/*/details.yaml")

CATEGORY_START_DECISION = re.compile(r"d\s*e\s*c", re.I)
CATEGORY_START_RESOLUTION = re.compile(r"r\s*e\s*s", re.I)
COMPOSITION_START_DIVISION = re.compile(r"div", re.I)
COMPOSITION_START_ENBANC = re.compile(r"en", re.I)


## Numbers

VOTEFULL_MIN_LENGTH = 20
VOTELINE_MIN_LENGTH = 15
VOTELINE_MAX_LENGTH = 1000

## Database

db = Database("cases.db", use_counts_table=True)

## Table names
DECISION_TBL = os.getenv("DECISION_TBL", "decisions_tbl")
CITATION_TBL = os.getenv("CITATION_TBL", "decision_citations_tbl")
VOTELINE_TBL = os.getenv("VOTELINE_TBL", "decision_votelines_tbl")
TITLETAG_TBL = os.getenv("TITLETAG_TBL", "decision_tags_tbl")
TITLELINE_TBL = os.getenv("TITLELINE_TBL", "decision_titlelines_tbl")

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