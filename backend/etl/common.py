"""Shared ETL helpers. Each source (NEA, SFA, HPB) is its own module that can be run
and updated on its own (NFR-10). ETL runs outside the request path; the API only
reads what's already in the database."""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.geo import postal_codes
from app.models import HawkerCentre, SyncRun

DATASTORE = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download"

NIL = re.compile(r"^\s*(nil|na|n\.a\.|-|tbc|tba|)\s*$", re.I)


def clean(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return None if NIL.match(s) else s


def centres_by_postal(db: Session) -> dict[str, HawkerCentre]:
    """Postal code -> centre, including the second block's code for two-block centres."""
    out: dict[str, HawkerCentre] = {}
    for c in db.scalars(select(HawkerCentre)):
        for pc in {c.postal_code, *postal_codes(c.street_address)} - {None}:
            out[pc] = c
    return out


def _client() -> httpx.Client:
    headers = {"accept": "application/json"}
    if key := get_settings().data_gov_api_key:
        headers["x-api-key"] = key
    return httpx.Client(headers=headers, timeout=60, follow_redirects=True)


def _get_json(client: httpx.Client, url: str, params: dict | None = None, retries: int = 4):
    for attempt in range(retries + 1):
        r = client.get(url, params=params)
        if r.status_code == 429 and attempt < retries:
            time.sleep(3 * (attempt + 1))  # public rate limit, back off
            continue
        r.raise_for_status()
        return r.json()


def fetch_all_rows(resource_id: str, page: int = 1000) -> list[dict]:
    rows: list[dict] = []
    with _client() as c:
        offset, total = 0, None
        while total is None or offset < total:
            j = _get_json(c, DATASTORE, {"resource_id": resource_id, "limit": page, "offset": offset})
            if not j.get("success"):
                raise RuntimeError(f"datastore_search failed for {resource_id}")
            recs = j["result"]["records"]
            total = j["result"].get("total", len(recs))
            rows.extend(recs)
            if not recs:
                break
            offset += len(recs)
    return rows


def fetch_geojson(dataset_id: str) -> dict:
    with _client() as c:
        poll = _get_json(c, POLL_DOWNLOAD.format(id=dataset_id))
        url = (poll.get("data") or {}).get("url")
        if not url:
            raise RuntimeError(f"No download URL for {dataset_id}: {poll.get('errorMsg')}")
        return _get_json(c, url)


@contextmanager
def sync_run(source: str, is_sample: bool = False) -> Iterator[tuple]:
    """Opens a DB session and logs the run to sync_run. On error the run is marked
    failed and existing data is left untouched (NFR-9: keep serving the last good copy)."""
    init_db()
    db = SessionLocal()
    run = SyncRun(source=source, is_sample=is_sample)
    db.add(run)
    db.commit()
    try:
        yield db, run
        run.status = "ok"
    except Exception as e:  # noqa: BLE001
        db.rollback()
        run.status = "failed"
        run.detail = f"{type(e).__name__}: {e}"[:2000]
        print(f"[{source}] FAILED: {run.detail}", file=sys.stderr)
        raise
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.close()
