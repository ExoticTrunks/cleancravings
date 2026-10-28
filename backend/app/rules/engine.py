"""Generic rule evaluator. Knows nothing about specific nutrients or conditions;
everything it needs comes from ClassificationRule rows. Adding a rule = adding a
row in etl/data/classification_rules.csv, no code change.

How a verdict is decided for one dish and one set of health conditions:
1. Applicable rules = GENERAL rules + rules for each of the user's conditions.
2. Each rule fires if `dish[nutrient] <operator> threshold`. Missing nutrient -> rule skipped
   and noted as a data gap.
3. The worst verdict among fired rules wins (AVOID > MODERATE > SUITABLE).
4. If a condition the user has could not be checked at all (every one of its rules lacked
   data), we can't call the dish SUITABLE or MODERATE for them: result is INSUFFICIENT_DATA,
   unless something already said AVOID.
"""

from __future__ import annotations

import operator as op
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

OPERATORS = {"<": op.lt, "<=": op.le, ">": op.gt, ">=": op.ge}
SEVERITY = {"SUITABLE": 0, "MODERATE": 1, "AVOID": 2}
GENERAL = "GENERAL"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    condition: str
    nutrient: str
    operator: str
    threshold: float
    unit: str
    verdict: str
    citation: str = ""

    def __post_init__(self) -> None:
        if self.operator not in OPERATORS:
            raise ValueError(f"{self.rule_id}: unknown operator {self.operator!r}")
        if self.verdict not in SEVERITY:
            raise ValueError(f"{self.rule_id}: rules can only output SUITABLE, MODERATE or AVOID")

    def fires(self, value: float) -> bool:
        return OPERATORS[self.operator](value, self.threshold)


@dataclass
class Finding:
    rule_id: str
    condition: str
    nutrient: str
    message: str
    verdict: str | None  # None = data gap
    citation: str


@dataclass
class Assessment:
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    missing_nutrients: list[str] = field(default_factory=list)
    unchecked_conditions: list[str] = field(default_factory=list)


def _fmt(x: float) -> str:
    return f"{x:g}"


def evaluate(nutrients: Mapping[str, float | None], rules: Iterable[Rule], conditions: Iterable[str] = ()) -> Assessment:
    wanted = {GENERAL, *(c.upper() for c in conditions)}
    applicable = [r for r in rules if r.condition in wanted]

    findings: list[Finding] = []
    missing: set[str] = set()
    checked_conditions: set[str] = set()
    worst: str | None = None

    for r in applicable:
        value = nutrients.get(r.nutrient)
        if value is None:
            missing.add(r.nutrient)
            continue
        checked_conditions.add(r.condition)
        if r.fires(value):
            findings.append(
                Finding(
                    rule_id=r.rule_id,
                    condition=r.condition,
                    nutrient=r.nutrient,
                    message=f"{r.nutrient.replace('_', ' ')} {_fmt(value)} {r.operator} {_fmt(r.threshold)} {r.unit}",
                    verdict=r.verdict,
                    citation=r.citation,
                )
            )
            if worst is None or SEVERITY[r.verdict] > SEVERITY[worst]:
                worst = r.verdict

    conditions_with_rules = {r.condition for r in applicable}
    unchecked = sorted(conditions_with_rules - checked_conditions)
    for n in sorted(missing):
        findings.append(
            Finding(rule_id="-", condition="-", nutrient=n, message=f"No {n.replace('_', ' ')} value yet", verdict=None, citation="")
        )

    if worst == "AVOID":
        verdict = "AVOID"
    elif unchecked or worst is None:
        verdict = "INSUFFICIENT_DATA"
    else:
        verdict = worst

    # Show the findings that decided the verdict first
    findings.sort(key=lambda f: -SEVERITY.get(f.verdict or "", -1))
    return Assessment(verdict=verdict, findings=findings, missing_nutrients=sorted(missing), unchecked_conditions=unchecked)
