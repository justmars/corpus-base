import datetime
from pathlib import Path
from typing import Iterator

import pytest
import yaml
from corpus_pax import Individual, init_person_tables
from sqlpyd import Connection

from corpus_base import build_sc_tables, setup_case

temppath = "tests/test.db"


@pytest.fixture
def individual_records(shared_datadir):  # same as corpus-pax
    details = shared_datadir.glob("members/**/details.yaml")
    items = [yaml.safe_load(i.read_bytes()) for i in details]
    t = datetime.datetime.now().timestamp()
    return [
        {"id": f"id-{ctx}", "created": t, "modified": t} | i
        for ctx, i in enumerate(items)
    ]


@pytest.fixture
def test_decisions_globbed(shared_datadir):
    return shared_datadir.glob("decisions/**/details.yaml")


def setup_db(conn: Connection, paths: Iterator[Path], persons: list[dict]):
    init_person_tables(conn)
    conn.add_records(Individual, persons)
    build_sc_tables(conn)
    for p in paths:
        setup_case(conn, p)
    return conn


def teardown_db(conn: Connection):
    conn.db.close()  # close the connection
    Path().cwd().joinpath(temppath).unlink()  # delete the file


@pytest.fixture
def session(test_decisions_globbed, individual_records):
    c = Connection(DatabasePath=temppath)  # type: ignore
    db = setup_db(c, test_decisions_globbed, individual_records)
    yield db
    teardown_db(db)
