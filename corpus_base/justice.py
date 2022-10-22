import datetime
from enum import Enum
from http import HTTPStatus
from pathlib import Path

import yaml
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta as rd
from loguru import logger
from pydantic import BaseModel, Field, validator
from sqlite_utils import Database
from sqlite_utils.db import Table

from .settings import CHIEF_DATES_VIEW, MAX_JUSTICE_AGE, settings


class Gender(str, Enum):
    male = "Male"
    female = "Female"
    other = "Unspecified"


class Suffix(str, Enum):
    jr = "Jr."
    sr = "Sr."
    third = "III"
    fourth = "IV"
    fifth = "V"
    sixth = "VI"


class Bio(BaseModel):
    first_name: str
    last_name: str
    suffix: Suffix | None = Field(None)
    full_name: str
    gender: Gender = Field(Gender.other)

    class Config:
        use_enum_values = True

    @classmethod
    def from_dict(cls, data: dict):
        sfx = data.pop("Suffix")
        return cls(
            first_name=data.pop("First Name"),
            last_name=data.pop("Last Name"),
            suffix=None if sfx == "" else sfx,
            full_name=data.pop("Justice"),
            gender=Gender(data.pop("Gender")),
        )


class Justice(Bio):
    id: int = Field(
        ...,
        title="Justice ID Identifier",
        description="Starting from 1, the integer represents the order of appointment to the Supreme Court.",
        ge=1,
        lt=1000,
    )
    alias: str | None = Field(
        None,
        title="Alias",
        description="Means of matching ponente and voting strings to the justice id.",
    )
    start_term: datetime.date | None = Field(
        None,
        title="Start Term",
        description="Date of appointment.",
    )
    end_term: datetime.date | None = Field(
        None,
        title="End Term",
        description="Date of termination.",
    )
    chief_date: datetime.date | None = Field(
        None,
        title="Date Appointed As Chief Justice",
        description="When appointed, the extension title of the justice changes from 'J.' to 'C.J'. for cases that are decided after the date of appointment but before the date of retirement.",
    )
    birth_date: datetime.date | None = Field(
        None,
        title="Date of Birth",
        description=f"The Birth Date is used to determine the retirement age of the justice. Under the 1987 constitution, this is {MAX_JUSTICE_AGE}. There are missing dates: see Jose Generoso 41, Grant Trent 14, Fisher 19, Moir 20.",
    )
    retire_date: datetime.date | None = Field(
        None,
        title="Mandatory Retirement Date",
        description="Based on the Birth Date, if it exists, it is the maximum term of service allowed by law.",
    )
    inactive_date: datetime.date | None = Field(
        None,
        title="Date",
        description="Which date is earliest inactive date of the Justice, the retire date is set automatically but it is not guaranteed to to be the actual inactive date. So the inactive date is either that specified in the `end_term` or the `retire_date`, whichever is earlier.",
    )

    @validator("retire_date")
    def retire_date_70_years(cls, v, values):
        if v and values["birth_date"]:
            if values["birth_date"] + rd(years=MAX_JUSTICE_AGE) != v:
                raise ValueError("Must be 70 years from birth date.")
        return v

    class Config:
        use_enum_values = True

    @classmethod
    def from_data(cls, data: dict):
        def extract_date(text: str | None) -> datetime.date | None:
            return parse(text).date() if text else None

        bio = Bio.from_dict(data)

        # Not all have aliases; default needed
        alias = data.pop("Alias", None)
        if not alias:
            if bio.last_name and bio.suffix:
                alias = f"{bio.last_name} {bio.suffix}".lower()

        retire_date = None
        if dob := extract_date(data.pop("Born")):
            retire_date = dob + rd(years=MAX_JUSTICE_AGE)

        # Assume that the retire_date is latest possible date of inactivity but if end_date is present, use this instead
        inactive_date = retire_date
        if end_date := extract_date(data.pop("End of term")):
            inactive_date = end_date or retire_date

        return cls(
            **bio.dict(exclude_none=True),
            id=data.pop("#"),
            alias=alias,
            birth_date=dob,
            start_term=extract_date(data.pop("Start of term")),
            end_term=end_date,
            chief_date=extract_date(data.pop("Appointed chief")),
            retire_date=retire_date,
            inactive_date=inactive_date,
        )

    @classmethod
    def make_table(cls, db):
        tbl = db[settings.JusticeTableName]
        if tbl.exists():
            return tbl
        tbl.create(
            columns={
                "id": int,
                "first_name": str,
                "last_name": str,
                "full_name": str,
                "suffix": str,
                "alias": str,
                "gender": str,
                "birth_date": datetime.date,
                "start_term": datetime.date,
                "end_term": datetime.date,
                "chief_date": datetime.date,
                "retire_date": datetime.date,
                "inactive_date": datetime.date,
            },
            pk="id",
            if_not_exists=True,
        )
        idx_prefix = "idx_justices_"
        indexes = [
            ["last_name", "alias", "start_term", "inactive_date"],
            ["start_term", "inactive_date"],
            ["last_name", "alias"],
            ["alias"],
            ["last_name"],
            ["full_name"],
            ["start_term"],
            ["end_term"],
            ["chief_date"],
            ["retire_date"],
            ["inactive_date"],
        ]
        for i in indexes:
            tbl.create_index(i, idx_prefix + "_".join(i), if_not_exists=True)
        tbl.enable_fts(
            ["full_name"],
            create_triggers=True,
            replace=True,
            tokenize="porter",
        )
        return tbl

    @classmethod
    def from_api(
        cls,
        file_to_create: Path = settings.local_justice_file,
        get_most_recent: bool = False,
    ) -> Path:
        # check local file
        if file_to_create.exists():
            if not get_most_recent:
                return file_to_create
            file_to_create.unlink()

        # extract the response
        resp = settings.call_api()
        if not resp:
            raise Exception(f"No response, check {settings.__annotations__=}")
        if not resp.status_code == HTTPStatus.OK:
            raise Exception(f"{resp.status_code=}, see settings.")

        # recreate objs in local file
        objects = (Justice.from_data(o) for o in yaml.safe_load(resp.content))
        data = [object.dict(exclude_none=True) for object in objects]
        with open(file_to_create, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
            return file_to_create

    @classmethod
    def from_local(cls) -> list["Justice"]:
        """List each justice from the cleaned up file; the file should be generated by `get_justice_data()`"""
        if settings.local_justice_file.exists():
            f = settings.local_justice_file.read_bytes()
            items = yaml.safe_load(f)
            return [cls(**i) for i in items]
        raise Exception(f"Need file to exist: {settings.local_justice_file=}")

    @classmethod
    def init_justices_tbl(cls) -> Database:
        """Add a table containing names and ids of justices; alter the original decision's table for it to include a justice id."""
        db = settings.db
        justice_tbl = db[settings.JusticeTableName]
        if justice_tbl.exists() and isinstance(justice_tbl, Table):
            # add all records from the local file to the created justice table
            justice_tbl.insert_all(i.dict() for i in Justice.from_local())
        return db

    @classmethod
    def get_active_on_date(cls, target_date: str) -> list[dict]:
        """Get list of justices that have been appointed before the `target date` and have not yet become inactive."""
        try:
            valid_date = parse(target_date).date().isoformat()
        except:
            raise Exception(f"Need {target_date=}")
        db = settings.db
        tbl = db[settings.JusticeTableName]
        if tbl.exists():
            return list(
                tbl.rows_where(
                    "inactive_date > :date and :date > start_term",
                    {"date": valid_date},
                    select="id, lower(last_name) surname, alias, start_term, inactive_date, chief_date",
                    order_by="start_term desc",
                )
            )
        raise Exception(f"Need valid {tbl=}")

    @classmethod
    def get_justice_on_date(
        cls, target_date: str, cleaned_name: str
    ) -> dict | None:
        """Based on `get_active_on_date()`, match the cleaned_name to either the alias of the justice or the justice's last name; on match, determine whether the designation should be 'C.J.' or 'J.'"""
        candidate_options = cls.get_active_on_date(target_date)
        opts = []
        for c in candidate_options:
            if c["alias"] and c["alias"] == cleaned_name:
                opts.append(c)
                continue
            elif c["surname"] == cleaned_name:
                opts.append(c)
                continue
        if opts:
            if len(opts) == 1:
                res = opts[0]
                res.pop("alias")
                res["surname"] = res["surname"].title()
                res["designation"] = "J."
                target = parse(target_date).date()
                if chief_date := res.get("chief_date"):
                    s = parse(chief_date).date()
                    e = parse(res["inactive_date"]).date()
                    if s < target < e:
                        res["designation"] = "C.J."
                return res
            else:
                msg = f"Many {opts=} for {cleaned_name=} on {target_date=}"
                logger.warning(msg)
        return None

    @classmethod
    def view_chiefs(cls) -> list[dict]:
        """Get general information of the chief justices and their dates of appointment."""
        db = settings.db
        view = CHIEF_DATES_VIEW
        if view in db.view_names():
            return list(db[view].rows)
        sqlpath = Path(__file__).parent / "sql_templates" / "chief_dates.sql"
        db.create_view(view, sql=sqlpath.read_text())
        return list(db[view].rows)
