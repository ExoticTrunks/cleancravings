"""Lab 4: one test per row in classification_rules.csv, generated from the data.
Add a rule to the CSV and it gets a test automatically."""

import pytest

from app.rules.engine import Rule, evaluate
from etl.seed_reference import read_dishes, read_rules

RULES = [Rule(r["rule_id"], r["condition"], r["nutrient"], r["operator"], r["threshold"], r["unit"], r["verdict"], r["citation"]) for r in read_rules()]
EPS = 0.5


def _firing_value(r: Rule) -> float:
    return {"<": r.threshold - EPS, "<=": r.threshold, ">": r.threshold + EPS, ">=": r.threshold}[r.operator]


def _non_firing_value(r: Rule) -> float:
    return {"<": r.threshold, "<=": r.threshold + EPS, ">": r.threshold, ">=": r.threshold - EPS}[r.operator]


@pytest.mark.parametrize("rule", RULES, ids=[r.rule_id for r in RULES])
def test_rule_boundaries(rule: Rule):
    assert rule.fires(_firing_value(rule)), "should fire on its side of the threshold"
    assert not rule.fires(_non_firing_value(rule)), "boundary value must fall on the other side"


@pytest.mark.parametrize("rule", RULES, ids=[r.rule_id for r in RULES])
def test_rule_drives_verdict(rule: Rule):
    """With only this rule's condition rules loaded, a value that fires this rule gives at
    least this rule's severity."""
    same = [r for r in RULES if r.condition == rule.condition and r.nutrient == rule.nutrient]
    cond = [] if rule.condition == "GENERAL" else [rule.condition]
    a = evaluate({rule.nutrient: _firing_value(rule)}, same, cond)
    sev = {"SUITABLE": 0, "MODERATE": 1, "AVOID": 2}
    assert sev[a.verdict] >= sev[rule.verdict]
    assert any(f.rule_id == rule.rule_id for f in a.findings)


@pytest.mark.parametrize("rule", RULES, ids=[r.rule_id for r in RULES])
def test_rule_has_citation(rule: Rule):
    assert rule.citation.strip(), "every rule needs a citation or a TBC note (traceability)"


def test_bands_cover_every_value_without_gaps():
    """Each (condition, nutrient) band set should give a verdict for any value."""
    groups = {}
    for r in RULES:
        groups.setdefault((r.condition, r.nutrient), []).append(r)
    for (cond, nutrient), rules in groups.items():
        if len(rules) < 2:
            continue  # single 'flag' rules like G-KCAL-01 are allowed
        for v in [0, *(r.threshold for r in rules), *(r.threshold + EPS for r in rules), 10_000]:
            assert any(r.fires(v) for r in rules), f"{cond}/{nutrient} has a gap at {v}"


# ----- engine behaviour (verdict combination) -----

GEN = [r for r in RULES if r.condition == "GENERAL"]
HTN = [r for r in RULES if r.condition in ("GENERAL", "HYPERTENSION")]


@pytest.mark.parametrize(
    "sodium,conditions,expected",
    [
        (300, [], "SUITABLE"),
        (1287, [], "MODERATE"),  # chicken rice
        (2913, [], "AVOID"),  # fishball noodle soup
        (600, ["HYPERTENSION"], "SUITABLE"),
        (880, ["HYPERTENSION"], "MODERATE"),
        (1600, ["HYPERTENSION"], "AVOID"),
    ],
)
def test_sodium_verdicts(sodium, conditions, expected):
    assert evaluate({"sodium_mg": sodium}, RULES, conditions).verdict == expected


def test_missing_data_for_users_condition_is_insufficient():
    a = evaluate({"sodium_mg": 300}, RULES, ["DIABETES"])
    assert a.verdict == "INSUFFICIENT_DATA"
    assert a.unchecked_conditions == ["DIABETES"]
    assert "sugar_g" in a.missing_nutrients


def test_avoid_wins_even_with_missing_data():
    assert evaluate({"sodium_mg": 2500}, RULES, ["DIABETES"]).verdict == "AVOID"


def test_no_data_at_all():
    assert evaluate({}, RULES, []).verdict == "INSUFFICIENT_DATA"


def test_bad_rule_rows_are_rejected():
    with pytest.raises(ValueError):
        Rule("X", "GENERAL", "sodium_mg", "=>", 1, "mg", "AVOID")
    with pytest.raises(ValueError):
        Rule("X", "GENERAL", "sodium_mg", ">", 1, "mg", "INSUFFICIENT_DATA")


def test_dish_csv_is_clean():
    dishes = read_dishes()
    names = [d["dish_name"] for d in dishes]
    assert len(names) == len(set(names))
    assert all(d["source"] for d in dishes)
