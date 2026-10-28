"""Load the team-maintained reference data: dish profiles and classification rules.
Non-coders can edit the two CSVs in etl/data/ and re-run this; no Python needed.

    python -m etl.seed_reference
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClassificationRule, DishType, Verdict
from app.rules.engine import Rule

from .common import sync_run

DATA = Path(__file__).parent / "data"
NUM = ("serving_g", "energy_kcal", "sodium_mg", "sugar_g", "saturated_fat_g", "protein_g")


def read_rules(path: Path = DATA / "classification_rules.csv") -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["threshold"] = float(r["threshold"])
        Rule(r["rule_id"], r["condition"], r["nutrient"], r["operator"], r["threshold"], r["unit"], r["verdict"])  # validates
    ids = [r["rule_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule_id in classification_rules.csv")
    return rows


def read_dishes(path: Path = DATA / "dish_types.csv") -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in NUM:
            r[k] = float(r[k]) if r.get(k, "").strip() else None
        for k in ("contains_pork", "contains_beef", "is_vegetarian"):
            r[k] = r.get(k, "0").strip() in ("1", "true", "True", "yes")
    return rows


def load(db: Session) -> int:
    n = 0
    for r in read_rules():
        obj = db.get(ClassificationRule, r["rule_id"]) or ClassificationRule(rule_id=r["rule_id"])
        for k in ("condition", "nutrient", "operator", "threshold", "unit", "citation", "status"):
            setattr(obj, k, r[k])
        obj.verdict = Verdict(r["verdict"])
        db.add(obj)
        n += 1
    keep = {r["rule_id"] for r in read_rules()}
    for old in db.scalars(select(ClassificationRule)).all():
        if old.rule_id not in keep:
            db.delete(old)
    for r in read_dishes():
        obj = db.scalars(select(DishType).where(DishType.dish_name == r["dish_name"])).first() or DishType()
        for k, v in r.items():
            setattr(obj, k, v)
        db.add(obj)
        n += 1
    db.commit()
    return n


def main() -> None:
    with sync_run("REF") as (db, run):
        run.rows = load(db)
        print(f"[REF] loaded {run.rows} rules + dish types")


if __name__ == "__main__":
    main()
