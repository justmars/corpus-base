from pylts import ConfigS3
from collections.abc import Callable, Iterator
from pathlib import Path
import sys
import click
import yaml
from corpus_pax import Individual, setup_pax
from corpus_pax.utils import delete_tables_with_prefix
from corpus_sc_toolkit import (
    DECISION_PATH,
    InterimDecision,
    Justice,
    get_justices_file,
)
from loguru import logger
from pydantic import BaseModel
from sqlpyd import Connection

from .main import (
    CitationRow,
    DecisionRow,
    OpinionRow,
    SegmentRow,
    TitleTagRow,
    VoteLine,
)


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
        {
            "sink": sys.stderr,
            "format": "{message}",
            "level": "DEBUG",
            "serialize": True,
        },
    ]
)


class CorpusDecision(BaseModel):
    """Accepts the following fields:

    Field | Type | Description
    --:|:--:|:--
    conn | sqlpyd.Connection | Database to add decisions to; _must be previously populated by PDF tables_
    test | int (defaults to 0) | If specified, the number of decisions to add to the database object
    rebuild | bool (defaults to False) | If True, rebuild the database from scratch

    Notes:

    Property | Type | Description
    --:|:--:|:--
    `@paths` | Iterator[Path] | Assumes a local path to *.yaml files
    `@pdfs` | Iterator[InterimDecision] | Content will be sourced from PDF tables
    """  # noqa: E501

    conn: Connection
    test: int = 0
    rebuild: bool = False

    @property
    def paths(self) -> Iterator[Path]:
        return DECISION_PATH.glob("**/*/details.yaml")

    @property
    def pdfs(self) -> Iterator[InterimDecision]:
        return InterimDecision.limited_decisions(self.conn.db)

    def setup(self):
        """Since there are thousands of cases, limit the number of objects
        via the `test_num`."""
        db = str(self.conn.db)
        if self.rebuild:
            logger.info(f"Rebuilding database in {db=}")
            delete_tables_with_prefix(self.conn, ["pax", "sc"])
            setup_pax(str(self.conn.path_to_db))
            self.build_tables()
        else:
            logger.info(f"Start decision creation in {db=}")
        self.add(self.paths, self.add_path)
        self.add(self.pdfs, self.add_pdf)

    def build_tables(self):
        """Create all the relevant tables involving a decision object."""
        justices = yaml.safe_load(get_justices_file().read_bytes())
        self.conn.add_records(Justice, justices)
        self.conn.create_table(DecisionRow)
        self.conn.create_table(CitationRow)
        self.conn.create_table(OpinionRow)
        self.conn.create_table(VoteLine)
        self.conn.create_table(TitleTagRow)
        self.conn.create_table(SegmentRow)
        self.conn.db.index_foreign_keys()

    def add(self, items: Iterator[InterimDecision | Path], func_add: Callable):
        """Use `func_add()` on each of the `items`, limited count by the
        `self.test`, if declared."""
        for counter, item in enumerate(items):
            if self.test and counter == self.test:
                logger.info(f"Test add: {counter=}")
                break
            try:
                func_add(item)
            except Exception as e:
                logger.info(e)

    def build_decision(self, item_obj: InterimDecision | Path) -> str | None:
        """Based on the type of object, create the `DecisionRow` and using this
        structure, create all the other meta objects."""

        # Create the DecisionRow
        if isinstance(item_obj, Path):
            obj = DecisionRow.from_path(c=self.conn, p=item_obj)
        elif isinstance(item_obj, InterimDecision):
            obj = DecisionRow.from_pdf(obj=item_obj)
        if not obj:
            logger.error(f"Skipping bad {item_obj=};")
            return None

        # Each DecisionRow will have related meta objects
        decision_id = obj.add_meta(conn=self.conn)
        if not decision_id:
            logger.error(f"Could not setup {obj.id=}; {obj.origin=}")
            return None

        return decision_id

    def add_pdf(self, pdf_obj: InterimDecision):
        """Parse a case's pre-processed pdf found in the `pdf_obj`."""
        if not self.build_decision(pdf_obj):
            return
        for op in pdf_obj.opinions:
            self.conn.add_record(kls=OpinionRow, item=op.row)
            for segment in op.segments:
                self.conn.add_record(kls=SegmentRow, item=segment._asdict())

    def add_path(self, path_obj: Path):
        """Parse a case's `details.yaml` found in the `path_obj`."""
        if not (pk := self.build_decision(path_obj)):
            return
        j_id = self.conn.table(DecisionRow).get(pk).get("justice_id")
        to_fix = {"concurs", "tags"}  # TODO: handle new features later
        for op in OpinionRow.get_opinions(path_obj.parent, pk, j_id):
            self.conn.add_record(kls=OpinionRow, item=op.dict(exclude=to_fix))
            self.conn.add_records(kls=SegmentRow, items=op.segments)


def add_authors_only(c: Connection):
    """Helper function for just adding the author decision m2m table."""
    case_details = DECISION_PATH.glob("**/*/details.yaml")
    for detail_path in case_details:
        if obj := DecisionRow.from_path(c, detail_path):
            for email in obj.emails:  # assign author row to a joined m2m table
                tbl = c.table(DecisionRow)
                if tbl.get(obj.id):
                    tbl.update(obj.id).m2m(
                        other_table=c.table(Individual),
                        lookup={"email": email},
                        pk="id",
                        m2m_table="sc_tbl_decisions_pax_tbl_individuals",
                    )


@click.group()
def cli():
    ...


def restore_conn(dbfolder: str) -> Connection:
    """Get the Connection object to the database restored."""
    logger.info("Starting setup of corpus-base by restoration.")
    stream = ConfigS3(s3="s3://corpus-pdf/db", folder=Path().cwd() / dbfolder)
    stream.restore()
    return Connection(DatabasePath=str(stream.dbpath), WAL=True)


@cli.command()
@click.option("--dbfolder", default="data", help="Location of the database.")
@click.option("--test", default=0, help="If 0, will add all entries found.")
@click.option(
    "--rebuild",
    default=True,
    help="If True, will create database from scratch.",
)
def prep(dbfolder, test, rebuild):
    conn = restore_conn(dbfolder)
    corpus = CorpusDecision(conn=conn, test=test, rebuild=rebuild)
    corpus.setup()


@cli.command()
@click.option("--dbfolder", default="data", help="Location of the database.")
def test(dbfolder):
    conn = restore_conn(dbfolder)
    corpus = CorpusDecision(conn=conn, test=5, rebuild=True)
    corpus.setup()


@cli.command()
@click.option("--dbfolder", default="data", help="Location of the database.")
@click.option("--test", default=0, help="If 0, will add all entries found.")
def rebuild(dbfolder, test):
    conn = restore_conn(dbfolder)
    corpus = CorpusDecision(conn=conn, test=test, rebuild=True)
    corpus.setup()
