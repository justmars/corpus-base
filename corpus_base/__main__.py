from corpus_pax import setup_pax
from corpus_pax.utils import delete_tables_with_prefix
from loguru import logger
from sqlpyd import Connection

from .main import add_cases, build_sc_tables

logger.configure(
    handlers=[
        {
            "sink": "logs/error.log",
            "format": "{message}",
            "level": "ERROR",
        },
        {
            "sink": "logs/warnings.log",
            "format": "{message}",
            "level": "WARNING",
            "serialize": True,
        },
    ]
)


def setup_base(db_path: str, test_num: int | None = None) -> Connection:
    """Recreates tables and populates the same.

    Since there are thousands of cases, limit the number of downloads
    via the `test_num`.

    Args:
        db_path (str): string path from the cwd
        test_num (int | None, optional): e.g. how many cases will it
            add to the database. Defaults to None.

    Returns:
        Connection: sqlpyd wrapper sqlite.utils Database
    """
    c = Connection(DatabasePath=db_path, WAL=True)  # type: ignore
    delete_tables_with_prefix(c, ["sc"])
    build_sc_tables(c)
    if test_num:
        add_cases(c, test_num)
    else:
        add_cases(c)
    return c


def setup_pax_base(db_path: str) -> Connection:
    setup_pax(db_path)
    return setup_base(db_path)
