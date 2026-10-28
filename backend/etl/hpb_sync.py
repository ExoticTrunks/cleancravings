"""RETIRED, kept for reference. Replaced by hpb_partners_sync.py: this layer is mostly
chain outlets and only placed 16 outlets at hawker centres, none at a known stall.

Healthier Dining Programme outlets from HPB's "Healthier Eateries" GeoJSON on data.gov.sg.

    python -m etl.hpb_sync
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ParticipatingStall, Stall

from .common import centres_by_postal, clean, fetch_geojson, sync_run

DATASET = "d_2925c2ccf75d1c135c2d469e0de3cee6"
_TABLE_RE = re.compile(r"<th>\s*([^<]*?)\s*</th>\s*<td>\s*([^<]*?)\s*</td>", re.I)
# The live dataset puts this same sentence in DESCRIPTION for every outlet, so it says
# nothing about the outlet's participation category
_GENERIC_DESC = re.compile(r"^choose healthier options from", re.I)


def _pad(part: str) -> str:
    return part.zfill(2) if part.isdigit() else part


def parse_feature(f: dict) -> dict:
    """data.gov.sg GeoJSON comes either with flat properties (NAME, ADDRESSPOSTALCODE...)
    or KML-style with everything inside an HTML table in 'Description'. Handle both."""
    p = dict(f.get("properties") or {})
    if not p.get("NAME") and (desc := p.get("Description") or p.get("description")):
        p.update({k.upper(): v for k, v in _TABLE_RE.findall(desc)})
    coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
    pc = clean(p.get("ADDRESSPOSTALCODE"))
    floor, unit = clean(p.get("ADDRESSFLOORNUMBER")), clean(p.get("ADDRESSUNITNUMBER"))
    # Live data has floor "1", unit "3" (or "5, 12" for a double unit); SFA addresses give
    # "#01-03", so pad both parts and keep the first unit to match stalls
    unit = unit.split(",")[0].strip() if unit else None
    category = clean(p.get("DESCRIPTION"))
    return dict(
        outlet_name=clean(p.get("NAME")) or "Healthier eatery",
        postal_code=str(int(float(pc))).zfill(6) if pc and re.fullmatch(r"[\d.]+", pc) else None,
        unit_number=f"{_pad(floor)}-{_pad(unit)}".upper() if floor and unit else None,
        participation_category=None if category and _GENERIC_DESC.match(category) else category,
        longitude=float(coords[0]) if coords[0] is not None else None,
        latitude=float(coords[1]) if coords[1] is not None else None,
    )


def load(db: Session, features: list[dict]) -> int:
    by_postal = centres_by_postal(db)
    stalls = {(s.centre_id, s.unit_number): s for s in db.scalars(select(Stall)) if s.unit_number}
    db.execute(delete(ParticipatingStall))  # full refresh each run
    n = 0
    for f in features:
        o = parse_feature(f)
        # Postal code only. Matching by distance pulled in chain outlets from malls and
        # blocks next door (most of the live dataset is chains, not hawker stalls)
        centre = by_postal.get(o["postal_code"])
        if centre is None:
            continue  # restaurants etc. outside hawker centres
        stall = stalls.get((centre.id, o["unit_number"]))
        db.add(ParticipatingStall(**o, centre_id=centre.id, stall_id=stall.id if stall else None))
        n += 1
    db.commit()
    return n


def main() -> None:
    with sync_run("HPB") as (db, run):
        run.rows = load(db, fetch_geojson(DATASET).get("features", []))
        print(f"[HPB] matched {run.rows} healthier outlets to hawker centres")


if __name__ == "__main__":
    main()
