from pathlib import Path

import pytest
from sqlite_utils import Database
from sqlpyd import Connection

from corpus_base import Justice, setup_base_tbls, setup_case

"""
@pytest.fixture
def test_db() -> Connection:
    case = (
        Path(__file__).parent / "decisions" / "sc" / "62055" / "details.yaml"
    )
    conn = Connection(DatabasePath="tests/testing.db", WALMode=False)
    Justice.init_justices_tbl(conn, Path(__file__).parent / "test_sc.yaml")
    conn.path_to_db.unlink()
    return conn
"""
