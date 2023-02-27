import yaml
from collections.abc import Iterator
from typing import Any
from pathlib import Path
from start_sdk import CFR2_Bucket
import datetime

TEMP_FOLDER = Path(__file__).parent.parent / "tmp"
TEMP_FOLDER.mkdir(exist_ok=True)

bucket_name = "sc-decisions"
origin = CFR2_Bucket(name=bucket_name)
meta = origin.resource.meta
if not meta:
    raise Exception("Bad bucket.")

client = meta.client
bucket = origin.bucket
dockets: list[str] = ["GR", "AM", "OCA", "AC", "BM"]
years: tuple[int, int] = (1902, datetime.datetime.now().date().year)
months = range(1, 13)


def get_dated_prefixes(
    dockets: list[str] = dockets, years: tuple[int, int] = years
) -> Iterator[str]:
    for docket in dockets:
        cnt_year, end_year = years[0], years[1]
        while cnt_year <= end_year:
            for month in months:
                yield f"{docket}/{cnt_year}/{month}/"
            cnt_year += 1


def iter_collections(
    dockets: list[str] = dockets, years: tuple[int, int] = years
) -> Iterator[dict]:
    for prefix in get_dated_prefixes(dockets, years):
        yield client.list_objects_v2(
            Bucket=bucket_name, Delimiter="/", Prefix=prefix
        )


def tmp_load(src: str, ext: str = "yaml") -> str | dict | None:
    path = TEMP_FOLDER / f"temp.{ext}"
    origin.download(src, str(path))
    content = None
    if ext == "yaml":
        content = yaml.safe_load(path.read_bytes())
    elif ext in ["md", "html"]:
        content = path.read_text()
    path.unlink(missing_ok=True)
    return content


def get_opinions(base_prefix: str) -> Iterator[dict]:
    result = client.list_objects_v2(
        Bucket=bucket_name, Delimiter="/", Prefix=f"{base_prefix}opinions/"
    )
    for content in result["Contents"]:
        src = content["Key"]
        k = src.split("/")[-1].split(".")[0]
        v = tmp_load(src, ext="md")
        yield {k: v}


def get_content(prefix: str) -> dict[str, Any]:
    data = tmp_load(f"{prefix}details.yaml")
    if not isinstance(data, dict):
        raise Exception(f"Bad details.yaml from {prefix=}")
    data["id"] = prefix.removesuffix("/").replace("/", "-").lower()
    data["opinions"] = list(get_opinions(prefix))
    return data


def get_contents(
    dockets: list[str] = dockets, years: tuple[int, int] = years
) -> Iterator[dict]:
    for collection in iter_collections(dockets, years):
        for docket in collection["CommonPrefixes"]:
            yield get_content(docket["Prefix"])
