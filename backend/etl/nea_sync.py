"""NEASyncController: hawker centres + closure periods from NEA's
"Dates of Hawker Centres Closure" dataset (one row per centre, with coordinates).

    python -m etl.nea_sync
"""

from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.geo import postal_code, region_for
from app.models import ClosurePeriod, ClosureReasonType, HawkerCentre

from .common import clean, fetch_all_rows, sync_run

DATASET = "d_bda4baa634dd1cc7a6c7cad5f19e2d68"
RR = re.compile(r"repair|redecorat|r\s*&\s*r", re.I)


def parse_date(s) -> date | None:
    s = clean(s)
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None  # e.g. "TBC": no alert until NEA confirms (UC-8.0 EX.3)


def parse_row(row: dict) -> tuple[dict, list[dict]]:
    """Pure function: one NEA row -> (centre fields, closure fields). Unit tested."""
    lat, lng = float(row["latitude_hc"]), float(row["longitude_hc"])
    address = clean(row.get("address_myenv"))
    centre = dict(
        id=int(row.get("_id") or row["serial_no"]),
        centre_name=clean(row.get("name")) or "Unnamed hawker centre",
        street_address=address,
        postal_code=postal_code(address),
        region=region_for(lat, lng),
        latitude=lat,
        longitude=lng,
        number_of_stalls=int(float(clean(row.get("no_of_food_stalls")) or 0)),
        photo_url=clean(row.get("photourl")),
        nea_status=clean(row.get("status")) or "Unknown",
    )
    closures: list[dict] = []
    for q in ("q1", "q2", "q3", "q4"):
        start = parse_date(row.get(f"{q}_cleaningstartdate"))
        if not start:
            continue
        end = parse_date(row.get(f"{q}_cleaningenddate")) or start
        remarks = clean(row.get(f"remarks_{q}"))
        closures.append(
            dict(
                start_date=start,
                end_date=end,
                reason_type=ClosureReasonType.REPAIRS_AND_REDECORATION
                if remarks and RR.search(remarks)
                else ClosureReasonType.SPRING_CLEANING,
                remarks=remarks,
                quarter=q.upper(),
                year=start.year,
            )
        )
    ow_start = parse_date(row.get("other_works_startdate"))
    if ow_start:
        remarks = clean(row.get("remarks_other_works"))
        closures.append(
            dict(
                start_date=ow_start,
                end_date=parse_date(row.get("other_works_enddate")) or ow_start,
                reason_type=ClosureReasonType.REPAIRS_AND_REDECORATION
                if remarks and RR.search(remarks)
                else ClosureReasonType.OTHER_WORKS,
                remarks=remarks,
                quarter=None,
                year=ow_start.year,
            )
        )
    return centre, closures


def load(db: Session, rows: list[dict]) -> int:
    n = 0
    for row in rows:
        try:
            centre_fields, closures = parse_row(row)
        except (KeyError, ValueError):
            continue  # skip rows without coordinates
        c = db.get(HawkerCentre, centre_fields["id"]) or HawkerCentre(id=centre_fields["id"])
        for k, v in centre_fields.items():
            setattr(c, k, v)
        db.add(c)
        db.flush()
        # Replace this centre's closures with the latest published set. Alerts reference
        # closure ids, so keep rows whose dates didn't change.
        existing = {(x.start_date, x.end_date, x.reason_type): x for x in db.scalars(select(ClosurePeriod).where(ClosurePeriod.centre_id == c.id))}
        keep: set[int] = set()
        for cl in closures:
            key = (cl["start_date"], cl["end_date"], cl["reason_type"])
            if key in existing:
                obj = existing[key]
                obj.remarks, obj.quarter, obj.year = cl["remarks"], cl["quarter"], cl["year"]
                keep.add(obj.id)
            else:
                db.add(ClosurePeriod(centre_id=c.id, **cl))
        stale = [x.id for x in existing.values() if x.id not in keep]
        if stale:
            db.execute(delete(ClosurePeriod).where(ClosurePeriod.id.in_(stale)))
        n += 1
    db.commit()
    return n


def main() -> None:
    with sync_run("NEA") as (db, run):
        run.rows = load(db, fetch_all_rows(DATASET))
        print(f"[NEA] synced {run.rows} hawker centres")


if __name__ == "__main__":
    main()
