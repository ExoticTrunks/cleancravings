"""Per-process cache for data that only changes when a sync runs or the day changes (NFR-1).

Building the centre and stall lists reads every stall, licence and grade (about 17,000 rows),
which takes seconds against the hosted database. Cached values are keyed on today's date and
the latest successful sync_run, so a finished sync or a new day rebuilds them on the next
request. Data changed outside a sync (e.g. by hand in the database) shows after a restart."""

from collections.abc import Callable
from datetime import date
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SyncRun

T = TypeVar("T")

_entries: dict[str, tuple[tuple, object]] = {}


def data_version(db: Session, today: date) -> tuple:
    return today, db.scalar(select(func.max(SyncRun.id)).where(SyncRun.status == "ok"))


def cached(name: str, db: Session, today: date, build: Callable[[], T]) -> T:
    key = data_version(db, today)
    hit = _entries.get(name)
    if hit is None or hit[0] != key:
        hit = (key, build())
        _entries[name] = hit
    return hit[1]  # type: ignore[return-value]
