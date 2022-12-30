import datetime
from collections.abc import Iterator
from pathlib import Path

import yaml
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta as rd
from loguru import logger
from pydantic import Field, validator
from sqlpyd import Connection, IndividualBio

from .utils import (
    CHIEF_DATES_VIEW,
    JUSTICE_LOCAL,
    MAX_JUSTICE_AGE,
    get_justices_from_api,
    sc_jinja_env,
)


class Bio(IndividualBio):
    @classmethod
    def from_dict(cls, data: dict):
        sfx = data.pop("Suffix")
        return cls(
            first_name=data.pop("First Name"),
            last_name=data.pop("Last Name"),
            suffix=None if sfx == "" else sfx,
            full_name=data.pop("Justice"),
            gender=data.pop("Gender"),
            nick_name=None,
        )


class Justice(Bio):
    __prefix__ = "sc"
    __tablename__ = "justices"
    __indexes__ = [
        ["last_name", "alias", "start_term", "inactive_date"],
        ["start_term", "inactive_date"],
        ["last_name", "alias"],
    ]

    id: int = Field(
        ...,
        title="Justice ID Identifier",
        description="Starting from 1, the integer represents the order of appointment to the Supreme Court.",
        ge=1,
        lt=1000,
        col=int,
    )
    alias: str | None = Field(
        None,
        title="Alias",
        description="Means of matching ponente and voting strings to the justice id.",
        col=str,
        index=True,
    )
    start_term: datetime.date | None = Field(
        None,
        title="Start Term",
        description="Date of appointment.",
        col=datetime.date,
        index=True,
    )
    end_term: datetime.date | None = Field(
        None,
        title="End Term",
        description="Date of termination.",
        col=datetime.date,
        index=True,
    )
    chief_date: datetime.date | None = Field(
        None,
        title="Date Appointed As Chief Justice",
        description="When appointed, the extension title of the justice changes from 'J.' to 'C.J'. for cases that are decided after the date of appointment but before the date of retirement.",
        col=datetime.date,
        index=True,
    )
    birth_date: datetime.date | None = Field(
        None,
        title="Date of Birth",
        description=f"The Birth Date is used to determine the retirement age of the justice. Under the 1987 constitution, this is {MAX_JUSTICE_AGE}. There are missing dates: see Jose Generoso 41, Grant Trent 14, Fisher 19, Moir 20.",
        col=datetime.date,
        index=True,
    )
    retire_date: datetime.date | None = Field(
        None,
        title="Mandatory Retirement Date",
        description="Based on the Birth Date, if it exists, it is the maximum term of service allowed by law.",
        col=datetime.date,
        index=True,
    )
    inactive_date: datetime.date | None = Field(
        None,
        title="Date",
        description="Which date is earliest inactive date of the Justice, the retire date is set automatically but it is not guaranteed to to be the actual inactive date. So the inactive date is either that specified in the `end_term` or the `retire_date`, whichever is earlier.",
        col=datetime.date,
        index=True,
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
    def validate_from_api(cls) -> Iterator["Justice"]:
        return (cls.from_data(i) for i in get_justices_from_api())

    @classmethod
    def extract_as_list(cls) -> list[dict]:
        return [i.dict(exclude_none=True) for i in cls.validate_from_api()]

    @classmethod
    def set_local_from_api(cls, local: Path = JUSTICE_LOCAL) -> Path:
        """Create a local .yaml file containing the list of validated Justices."""
        if local.exists():
            return local
        with open(local, "w") as writefile:
            yaml.safe_dump(
                data=cls.extract_as_list(),
                stream=writefile,
                sort_keys=False,
                default_flow_style=False,
            )
            return local

    @classmethod
    def init_justices_tbl(cls, c: Connection, p: Path = JUSTICE_LOCAL):
        """Add a table containing names and ids of justices; alter the original decision's table for it to include a justice id."""
        return c.add_records(Justice, yaml.safe_load(p.read_bytes()))

    @classmethod
    def get_active_on_date(cls, c: Connection, target_date: str) -> list[dict]:
        """Get list of justices that have been appointed before the `target date` and have not yet become inactive."""
        try:
            valid_date = parse(target_date).date().isoformat()
        except Exception:
            raise Exception(f"Need {target_date=}")
        return list(
            c.table(cls).rows_where(
                "inactive_date > :date and :date > start_term",
                {"date": valid_date},
                select="id, lower(last_name) surname, alias, start_term, inactive_date, chief_date",
                order_by="start_term desc",
            )
        )

    @classmethod
    def get_justice_on_date(
        cls, c: Connection, target_date: str, cleaned_name: str
    ) -> dict | None:
        """Based on `get_active_on_date()`, match the cleaned_name to either the alias of the justice or the justice's last name; on match, determine whether the designation should be 'C.J.' or 'J.'"""
        candidate_options = cls.get_active_on_date(c, target_date)
        opts = []
        for candidate in candidate_options:
            if candidate["alias"] and candidate["alias"] == cleaned_name:
                opts.append(candidate)
                continue
            elif candidate["surname"] == cleaned_name:
                opts.append(candidate)
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
    def view_chiefs(cls, c: Connection) -> list[dict]:
        """Get general information of the chief justices and their dates of appointment."""
        view = CHIEF_DATES_VIEW
        if view in c.db.view_names():
            return list(c.db[view].rows)
        c.db.create_view(
            view,
            sql=sc_jinja_env.get_template("chief_dates.sql").render(
                justice_table=Justice.__tablename__
            ),
        )
        return list(c.db[view].rows)
