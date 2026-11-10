"""SFASyncController: SAFE grades from SFA's "Track Records for Licensed Food
Establishments" search (https://www.sfa.gov.sg/tools-and-resources/track-records).

SFA has no open API for this, only an "Export to Excel" button. So the workflow is:
1. Search the portal (no filters, or by postal code), click Export to Excel.
2. Optionally do a second export with "Licence Suspended in the past 1 year" ticked.
3. Drop the file(s) in etl/inbox/ and run:

    python -m etl.sfa_import etl/inbox/track_records.xlsx [--suspended etl/inbox/suspended.xlsx] [--date 2026-10-13]

Only rows whose postal code matches a hawker centre are imported, and each becomes a
Cooked Food Stall. Every run adds a dated snapshot, which is how grade history builds up.
Columns in the real export: SNO, Establishment Address, Grade, Licence Number, Licensee
Name, Business Name, Type of Food Business. There's no postal code column, so it comes from
the address ("..., Singapore 050335"). A "Postal Code" column is used if present. Grades are
A / B / C / New, or NA.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo import postal_code as postal_from_address
from app.geo import today_sg, unit_number
from app.models import Licensee, SafeGradeValue, SAFEGrade, Stall, StallType

from .common import centres_by_postal, clean, sync_run

GRADE_RE = re.compile(r"^\s*(A|B|C|NEW)\s*(\(under review\))?\s*$", re.I)


def parse_grade(raw) -> tuple[SafeGradeValue, bool] | None:
    """'A' -> (A, False); 'New (Under Review)' -> (NEW, True); 'Not Under SAFE' -> None."""
    m = GRADE_RE.match(str(raw or ""))
    if not m:
        return None
    return SafeGradeValue(m.group(1).upper()), bool(m.group(2))


def _norm(h) -> str:
    return re.sub(r"[^a-z]", "", str(h or "").lower())


_XML_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")


def unescape(v):
    """The real export stores every cell OOXML-escaped ('335_x0020_SMITH_x0020_STREET_x0020__x0023_02-219')
    and openpyxl doesn't decode it, so turn _xHHHH_ back into the character."""
    return _XML_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), v) if isinstance(v, str) else v


def read_rows(path: Path) -> list[dict]:
    """Read an SFA export (xlsx or csv). The header row is found by looking for
    'Licence Number', since exports can have title rows above the table."""
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        ws = load_workbook(path, read_only=True, data_only=True).active
        table = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        with path.open(newline="", encoding="utf-8-sig") as f:
            table = list(csv.reader(f))
    for i, row in enumerate(table):
        headers = [_norm(unescape(h)) for h in row]
        if "licencenumber" in headers:
            out = []
            for r in table[i + 1 :]:
                rec = {headers[j]: unescape(r[j]) for j in range(min(len(headers), len(r)))}
                if clean(rec.get("licencenumber")):
                    out.append(rec)
            return out
    raise ValueError(f"{path}: couldn't find a 'Licence Number' header row")


def load(db: Session, rows: list[dict], snapshot: date, suspended: set[str] = frozenset()) -> int:
    centres = centres_by_postal(db)
    # Loaded once instead of three queries per row: looking up about 5,600 hawker rows one by one
    # took over 20 minutes against the hosted database, long enough for the connection to drop
    licensees = {x.licence_number: x for x in db.scalars(select(Licensee))}
    stalls: dict[str, Stall] = {}
    for s in db.scalars(select(Stall)):
        stalls.setdefault(s.licence_number, s)
    grades = {x.licence_number: x for x in db.scalars(select(SAFEGrade).where(SAFEGrade.snapshot_date == snapshot))}
    n = 0
    for r in rows:
        address = clean(r.get("establishmentaddress"))
        pc = clean(r.get("postalcode")) or postal_from_address(address)
        pc = pc.zfill(6) if pc else None
        centre = centres.get(pc)
        if centre is None:
            continue  # not at a hawker centre (restaurant, caterer, coffee shop...)
        lic_no = clean(r["licencenumber"]).upper()
        grade = parse_grade(r.get("grade"))

        lic = licensees.get(lic_no) or Licensee(licence_number=lic_no)
        licensees[lic_no] = lic
        lic.licensee_name = clean(r.get("licenseename"))
        lic.licence_status = "suspended" if lic_no in suspended else "active"
        if lic.last_seen_snapshot is None or snapshot >= lic.last_seen_snapshot:
            lic.last_seen_snapshot = snapshot
        db.add(lic)

        stall = stalls.get(lic_no) or Stall(licence_number=lic_no)
        stalls[lic_no] = stall
        stall.centre_id = centre.id
        stall.stall_name = clean(r.get("businessname")) or clean(r.get("licenseename")) or lic_no
        stall.unit_number = unit_number(address)
        stall.stall_type = StallType.COOKED_FOOD  # SFA only licenses food stalls; market stalls are NEA's
        db.add(stall)

        if grade:
            g = grades.get(lic_no) or SAFEGrade(licence_number=lic_no, snapshot_date=snapshot)
            grades[lic_no] = g
            g.grade_value, g.under_review = grade
            g.suspended_past_year = lic_no in suspended
            db.add(g)
        n += 1
    db.commit()
    return n


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=Path)
    ap.add_argument("--suspended", type=Path, help="second export filtered to 'suspended in past 1 year'")
    # SG date: the cron runs at 18:00 UTC, when date.today() on the runner is still yesterday
    ap.add_argument("--date", type=date.fromisoformat, default=today_sg())
    ap.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    suspended = {clean(r["licencenumber"]).upper() for r in read_rows(a.suspended)} if a.suspended else set()
    with sync_run("SFA", is_sample=a.sample) as (db, run):
        run.rows = load(db, read_rows(a.export), a.date, suspended)
        print(f"[SFA] imported {run.rows} hawker stalls (snapshot {a.date})")


if __name__ == "__main__":
    main()
