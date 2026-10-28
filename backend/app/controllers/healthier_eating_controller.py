"""HealthierEatingController (FR-4.x) plus dish recommendations (UC-6.0)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClassificationRule, DishType
from ..rules.engine import Rule, evaluate
from ..schemas import DishAssessment, DishListOut, FindingOut, Nutrients

NUTRIENTS = ("energy_kcal", "sodium_mg", "sugar_g", "saturated_fat_g", "protein_g")
VERDICT_ORDER = {"SUITABLE": 0, "MODERATE": 1, "INSUFFICIENT_DATA": 2, "AVOID": 3}

DISH_DISCLAIMER = (
    "Ratings use standard dish profiles and the team's own scoring against HPB guidance. "
    "Your stall's recipe may differ. General guidance, not medical advice."
)
# FR-4.4: never imply non-participating stalls are unhealthy
HDP_NOTE = "Joining the Healthier Dining Programme is voluntary. Stalls outside it aren't necessarily less healthy."


def _restricted(d: DishType, restrictions: set[str]) -> bool:
    if "NO_PORK" in restrictions and d.contains_pork:
        return True
    if "NO_BEEF" in restrictions and d.contains_beef:
        return True
    if "VEGETARIAN" in restrictions and not d.is_vegetarian:
        return True
    return False


class HealthierEatingController:
    @staticmethod
    def load_rules(db: Session) -> list[Rule]:
        return [
            Rule(r.rule_id, r.condition, r.nutrient, r.operator, r.threshold, r.unit, r.verdict.value, r.citation)
            for r in db.scalars(select(ClassificationRule)).all()
        ]

    @classmethod
    def assess_dishes(
        cls, db: Session, conditions: list[str], restrictions: list[str], prefer_lower_sodium: bool = False
    ) -> DishListOut:
        rules = cls.load_rules(db)
        excluded = 0
        out: list[DishAssessment] = []
        for d in db.scalars(select(DishType)).all():
            if _restricted(d, set(restrictions)):
                excluded += 1
                continue
            values = {n: getattr(d, n) for n in NUTRIENTS}
            a = evaluate(values, rules, conditions)
            out.append(
                DishAssessment(
                    id=d.id,
                    dish_name=d.dish_name,
                    category=d.category,
                    serving_g=d.serving_g,
                    nutrients=Nutrients(**values),
                    verdict=a.verdict,
                    findings=[FindingOut(**f.__dict__) for f in a.findings],
                    unchecked_conditions=a.unchecked_conditions,
                    contains_pork=d.contains_pork,
                    contains_beef=d.contains_beef,
                    is_vegetarian=d.is_vegetarian,
                    source=d.source,
                )
            )
        out.sort(
            key=lambda x: (
                VERDICT_ORDER[x.verdict.value],
                (x.nutrients.sodium_mg or 1e9) if prefer_lower_sodium else 0,
                x.dish_name,
            )
        )
        return DishListOut(
            conditions=conditions,
            restrictions=restrictions,
            dishes=out,
            excluded_by_restriction=excluded,
            disclaimer=DISH_DISCLAIMER,
        )
