import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from scrapers.models.data_model import ScrapeRun

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _serialise(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Cannot serialise {type(obj)}")


def save_run(run: ScrapeRun) -> Path:
    """Write a ScrapeRun to output/<timestamp>_<corridor>.json and return the path."""
    _OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = _OUTPUT_DIR / f"{ts}_{run.corridor}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(run.to_dict(), fh, indent=2, default=_serialise, ensure_ascii=False)
    print(f"  Saved → {path.name}")
    return path
