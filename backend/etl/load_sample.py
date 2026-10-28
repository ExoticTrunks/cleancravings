"""Load the bundled SAMPLE data through the same parsers as the real sync, so the app
works offline (UC-2.0 AC.2 / NFR-9 demo). Runs flagged as sample, and the app shows
a 'Sample data' banner. Never quote numbers from it.

    python -m etl.load_sample
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from app.geo import today_sg

from . import hpb_partners_sync, nea_sync, seed_reference, sfa_import
from .common import clean, sync_run

SAMPLE = Path(__file__).parent / "sample"
OFFSET = re.compile(r"^\{(-?\d+)\}$")


def _resolve_offsets(row: dict, today) -> dict:
    out = {}
    for k, v in row.items():
        m = OFFSET.match(str(v))
        out[k] = (today + timedelta(days=int(m.group(1)))).strftime("%d/%m/%Y") if m else v
    return out


def main() -> None:
    today = today_sg()
    with sync_run("REF") as (db, run):
        run.rows = seed_reference.load(db)
    with sync_run("NEA", is_sample=True) as (db, run):
        rows = json.loads((SAMPLE / "nea_closures.json").read_text())["rows"]
        run.rows = nea_sync.load(db, [_resolve_offsets(r, today) for r in rows])
    with sync_run("SFA", is_sample=True) as (db, run):
        susp = {clean(r["licencenumber"]).upper() for r in sfa_import.read_rows(SAMPLE / "sfa_suspended.csv")}
        sfa_import.load(db, sfa_import.read_rows(SAMPLE / "sfa_track_records_60d_ago.csv"), today - timedelta(days=60))
        run.rows = sfa_import.load(db, sfa_import.read_rows(SAMPLE / "sfa_track_records.csv"), today, susp)
    with sync_run("HPB", is_sample=True) as (db, run):
        outlets, _ = hpb_partners_sync.fetch_outlets(json.loads((SAMPLE / "hpb_partners.json").read_text(encoding="utf-8"))["rows"])
        counts = hpb_partners_sync.load(db, outlets, overrides=None)
        run.rows = counts.total() - counts["unmatched"]
    print("Sample data loaded. The app will show a 'Sample data' banner.")


if __name__ == "__main__":
    main()
