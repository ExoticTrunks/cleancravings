"""HPBSyncController: hawker stalls in HPB's Healthier Dining Programme, from the
"Healthier Dining Partners - F&B Partners" dataset on data.gov.sg. Replaces the
Healthier Eateries layer (hpb_sync.py), which is mostly chain outlets.

Hawker rows carry the centre's address (the same unit for every stall), so outlets are
matched to SFA stalls by name within the centre:
0. manual decisions in docs/hdp_match_overrides.csv (accept or reject an outlet/stall pair)
1. exact match on the normalised name (Brand_Name vs SFA business name)
2. otherwise a fuzzy match, accepted only if similarity >= FUZZY_MIN, at least FUZZY_MARGIN
   ahead of the runner-up, and the name minus generic dish words also agrees (DISTINCT_MIN)
3. otherwise the outlet stays at centre level (stall_id null)
Run after the SFA import, since it matches against SFA stalls.

    python -m etl.hpb_partners_sync --review   # writes docs/hdp_match_review.csv, no DB writes
    python -m etl.hpb_partners_sync
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.geo import postal_code
from app.models import HawkerCentre, Licensee, ParticipatingStall, Stall

from .common import centres_by_postal, clean, fetch_all_rows, sync_run

DATASET = "d_c475b9170c08f90580f4041bffd51639"
FUZZY_MIN = 0.90
FUZZY_MARGIN = 0.10  # "clearly better than the second-best candidate"
DISTINCT_MIN = 0.80  # the name with dish words removed must agree too
DOCS = Path(__file__).resolve().parents[2] / "docs"
REVIEW_CSV = DOCS / "hdp_match_review.csv"
OVERRIDES_CSV = DOCS / "hdp_match_overrides.csv"
REVIEW_EXACT_SAMPLE = 30

_SUFFIX = re.compile(r"[\s,.]*\b(pte\.?\s*ltd\.?|llp|enterprise|trading)[\s.]*$", re.I)
# Dish and stall-type words shared by many unrelated stalls. Without them, "Mei Xing Yong Tau Foo"
# vs "Mei Heng Yong Tau Foo" compares "mei xing" vs "mei heng", which is what tells them apart.
_GENERIC = re.compile(
    r"\b(economic rice|chicken rice|yong tau (foo|fu)|hainanese|fish ?balls?|noodles?|wan ?tons?|mee|prawns?"
    r"|teo ?chew|indian|muslim|food|gourmet|stall|kitchen|cent(re|er)|porridge|laksa|nasi)\b"
)


def strip_suffix(name: str | None) -> str:
    """'Poona Punjabi Dhaba Pte Ltd' -> 'Poona Punjabi Dhaba'. Repeats for 'X Enterprise Pte Ltd'."""
    name = name or ""
    while (stripped := _SUFFIX.sub("", name)) != name:
        name = stripped
    return name


def normalise(name: str | None) -> str:
    """Case, punctuation, spacing and company suffixes don't count:
    "Ah Hock's Mee-Pok Pte. Ltd." == "AH HOCKS MEE POK"."""
    return "".join(ch for ch in strip_suffix(name).casefold() if ch.isalnum())


def distinctive(name: str | None) -> str:
    """The normalised name without generic food words: 'Mei Xing Yong Tau Foo' -> 'meixing'."""
    words = re.sub(r"[^\w]+", " ", strip_suffix(name).casefold())
    return "".join(ch for ch in _GENERIC.sub(" ", words) if ch.isalnum())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_accepts(outlet: str, sfa: str, score: float, runner_up: float) -> bool:
    """Full-name score >= FUZZY_MIN, clearly ahead of the runner-up, and the distinctive part
    agrees (>= DISTINCT_MIN). If either name is nothing but generic words, the full score decides."""
    if score < FUZZY_MIN or score - runner_up < FUZZY_MARGIN:
        return False
    a, b = distinctive(outlet), distinctive(sfa)
    return not a or not b or similarity(a, b) >= DISTINCT_MIN


def drop_duplicates(rows: Iterable[dict]) -> list[dict]:
    """The feed repeats some rows verbatim (only _id differs)."""
    seen: set[tuple] = set()
    out = []
    for r in rows:
        key = tuple(sorted((k, v) for k, v in r.items() if k != "_id"))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def parse_row(row: dict) -> dict | None:
    """One feed row -> outlet fields, or None if it isn't a hawker stall."""
    if (clean(row.get("FnB_Setting")) or "").lower() != "hawker":
        return None
    # Category isn't read: it's "Hawker Food" on every hawker row, so it says nothing about cuisine
    address = clean(row.get("Outlet_Address"))
    criteria = clean(row.get("Menu_Item_Endorsement_Criteria"))
    return dict(
        outlet_id=row.get("_id"),
        outlet_name=clean(row.get("Brand_Name")) or clean(row.get("Name_of_Outlet")) or "Healthier Dining stall",
        address=address,
        postal_code=postal_code(address),
        participation_category=re.sub(r"\s+", " ", criteria) if criteria else None,
        # Unknown stays None, never False
        halal={"halal": True, "non-halal": False}.get((clean(row.get("Dining_Concept")) or "").lower()),
    )


class Candidate(NamedTuple):
    stall_id: int
    centre_id: int
    name: str
    licence_number: str


@dataclass
class Match:
    outlet: dict
    centre_id: int | None
    method: str | None = None  # "override" | "exact" | "fuzzy" | "centre" | "unmatched"
    stall: Candidate | None = None
    score: float | None = None
    runner_up: float | None = None
    distinct_score: float | None = None


def match_outlets(
    outlets: Iterable[dict],
    centre_by_postal: Mapping[str, int],
    stalls: Iterable[Candidate],
    overrides: Mapping[tuple[int, str], str] | None = None,
) -> list[Match]:
    """Pure function: outlets + {postal: centre_id} + SFA stalls + {(outlet_id, licence): accept|reject}
    -> one Match per outlet. Overrides beat the algorithm. Each stall is claimed by at most one outlet."""
    overrides = overrides or {}
    by_centre: dict[int, list[Candidate]] = defaultdict(list)
    by_licence: dict[str, Candidate] = {}
    for s in stalls:
        by_centre[s.centre_id].append(s)
        by_licence[s.licence_number] = s
    accepted = {oid: lic for (oid, lic), d in overrides.items() if d == "accept"}
    rejected = {k for k, d in overrides.items() if d == "reject"}
    results = [Match(o, centre_by_postal.get(o["postal_code"])) for o in outlets]
    claimed: set[int] = set()

    def open_to(m: Match, s: Candidate) -> bool:
        return s.stall_id not in claimed and (m.outlet["outlet_id"], s.licence_number) not in rejected

    for m in results:
        s = by_licence.get(accepted.get(m.outlet["outlet_id"]))
        if s and s.stall_id not in claimed:
            m.method, m.stall, m.centre_id = "override", s, s.centre_id
            claimed.add(s.stall_id)

    for m in results:
        if m.method is not None:
            continue
        if m.centre_id is None:
            m.method = "unmatched"
            continue
        key = normalise(m.outlet["outlet_name"])
        hits = [s for s in by_centre[m.centre_id] if normalise(s.name) == key and open_to(m, s)]
        # Two SFA stalls with the same name at one centre: can't tell which, leave it to the fuzzy pass (which rejects ties)
        if len(hits) == 1:
            m.method, m.stall, m.score = "exact", hits[0], 1.0
            claimed.add(hits[0].stall_id)

    proposals = []
    for m in results:
        if m.method is not None:
            continue
        key = normalise(m.outlet["outlet_name"])
        scored = sorted(
            ((similarity(key, normalise(s.name)), s) for s in by_centre[m.centre_id] if open_to(m, s)),
            key=lambda x: -x[0],
        )
        if not scored:
            continue
        best = scored[0][1]
        m.score, m.runner_up = scored[0][0], scored[1][0] if len(scored) > 1 else 0.0
        m.distinct_score = similarity(distinctive(m.outlet["outlet_name"]), distinctive(best.name))
        if fuzzy_accepts(m.outlet["outlet_name"], best.name, m.score, m.runner_up):
            proposals.append((m, best))
    # Strongest fuzzy matches claim their stall first
    for m, s in sorted(proposals, key=lambda p: -p[0].score):
        if s.stall_id not in claimed:
            m.method, m.stall = "fuzzy", s
            claimed.add(s.stall_id)

    for m in results:
        if m.method is None:
            m.method = "centre"
    return results


def read_overrides(outlets: Iterable[dict], path: Path = OVERRIDES_CSV) -> dict[tuple[int, str], str]:
    """docs/hdp_match_overrides.csv -> {(outlet_id, licence): decision}. outlet_id is the feed's _id,
    which is only a row number, so an override whose outlet_name no longer matches that row is
    skipped rather than applied to whatever outlet now has the id."""
    if not path.exists():
        return {}
    names = {o["outlet_id"]: o["outlet_name"] for o in outlets}
    out: dict[tuple[int, str], str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oid, decision = int(r["outlet_id"]), r["decision"].strip().lower()
            if decision not in ("accept", "reject"):
                raise ValueError(f"{path.name}: decision must be accept or reject, got {r['decision']!r}")
            if normalise(names.get(oid)) != normalise(r["outlet_name"]):
                print(f"[HPB] override skipped: outlet {oid} is no longer {r['outlet_name']!r}", file=sys.stderr)
                continue
            out[(oid, r["sfa_licence_number"].strip().upper())] = decision
    return out


def fetch_outlets(rows: list[dict] | None = None) -> tuple[list[dict], dict]:
    rows = fetch_all_rows(DATASET) if rows is None else rows
    deduped = drop_duplicates(rows)
    outlets = [o for o in (parse_row(r) for r in deduped) if o]
    return outlets, dict(rows=len(rows), duplicates=len(rows) - len(deduped), hawker=len(outlets))


def candidate_stalls(db: Session) -> list[Candidate]:
    # Only stalls with an SFA business name. Where the export had "NA", stall_name fell back
    # to the licensee's own name, which a brand name should never be matched against.
    rows = db.execute(
        select(Stall.id, Stall.centre_id, Stall.stall_name, Stall.licence_number)
        .join(Stall.licensee)
        .where(or_(Licensee.licensee_name.is_(None), Stall.stall_name != Licensee.licensee_name))
    ).all()
    return [Candidate(*r) for r in rows]


def _match(db: Session, outlets: list[dict], overrides: Path | None) -> list[Match]:
    centres = centres_by_postal(db)
    decisions = read_overrides(outlets, overrides) if overrides else {}
    return match_outlets(outlets, {pc: c.id for pc, c in centres.items()}, candidate_stalls(db), decisions)


def load(db: Session, outlets: list[dict], overrides: Path | None = OVERRIDES_CSV) -> Counter:
    """overrides=None for the sample feed, whose _ids have nothing to do with the real one's."""
    results = _match(db, outlets, overrides)
    db.execute(delete(ParticipatingStall))  # full refresh each run
    # halal only comes from this feed, so refresh it with the feed: a stall that left the
    # programme goes back to unknown
    db.execute(update(Stall).values(halal=None))
    for m in results:
        if m.centre_id is None:
            continue  # not at one of our hawker centres
        db.add(
            ParticipatingStall(
                outlet_name=m.outlet["outlet_name"],
                postal_code=m.outlet["postal_code"],
                unit_number=None,  # the feed's unit is the centre's address, not the stall's
                participation_category=m.outlet["participation_category"],
                centre_id=m.centre_id,
                stall_id=m.stall.stall_id if m.stall else None,
                match_method=m.method if m.stall else None,
            )
        )
        if m.stall and m.outlet["halal"] is not None:
            db.execute(update(Stall).where(Stall.id == m.stall.stall_id).values(halal=m.outlet["halal"]))
    db.commit()
    return Counter(m.method for m in results)


def _print_counts(counts: Counter, stats: dict) -> None:
    print(f"[HPB] {stats['rows']} rows, {stats['duplicates']} exact duplicates dropped, {stats['hawker']} hawker outlets")
    for k in ("override", "exact", "fuzzy", "centre", "unmatched"):
        print(f"  {k:10} {counts[k]}")


def review(path: Path = REVIEW_CSV) -> None:
    outlets, stats = fetch_outlets()
    db = SessionLocal()
    try:
        results = _match(db, outlets, OVERRIDES_CSV)
        names = {c.id: c.centre_name for c in db.scalars(select(HawkerCentre))}
    finally:
        db.close()

    fuzzy = sorted((m for m in results if m.method == "fuzzy"), key=lambda m: m.score)
    exact = [m for m in results if m.method == "exact"]
    sample = random.Random(2006).sample(exact, min(REVIEW_EXACT_SAMPLE, len(exact)))
    fmt = lambda x: "" if x is None else f"{x:.3f}"  # noqa: E731
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["outlet_id", "outlet_name", "sfa_licence_number", "sfa_name", "centre", "method",
                    "score", "runner_up_score", "distinct_score", "outlet_address"])
        for m in fuzzy + sample:
            w.writerow([m.outlet["outlet_id"], m.outlet["outlet_name"], m.stall.licence_number, m.stall.name,
                        names[m.centre_id], m.method, fmt(m.score), fmt(m.runner_up), fmt(m.distinct_score),
                        m.outlet["address"]])

    counts = Counter(m.method for m in results)
    _print_counts(counts, stats)
    print(f"  review file: {path} ({len(fuzzy)} fuzzy + {len(sample)} exact)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", action="store_true", help="write the match review CSV without touching the DB")
    a = ap.parse_args(argv)
    if a.review:
        review()
        return
    outlets, stats = fetch_outlets()
    with sync_run("HPB") as (db, run):
        counts = load(db, outlets)
        run.rows = counts.total() - counts["unmatched"]
        _print_counts(counts, stats)


if __name__ == "__main__":
    main()
