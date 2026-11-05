"""Lab 4 test cases (SC2006 Lab 4, 3.2): black-box and white-box testing.

- Black box: HygieneController.passes_threshold (FR-2.2, FR-2.5, FR-5.4), designed with
  equivalence classes and boundary values.
- White box (basis path): rules/engine.evaluate (dish verdicts, NFR-6) and
  ClosureController.centre_status (FR-3.2). Node numbers in the path comments match the
  control flow graphs in docs/lab4/.

Each case records its actual output before asserting. With LAB4_RESULTS=<file> set, the run
writes every row to that JSON file, which docs/lab4/make_test_report.py turns into the
Input / Expected / Actual tables of the Lab 4 report. Without it, these are ordinary tests.
"""

import json
import os
from dataclasses import dataclass
from datetime import date

import pytest

from app.controllers.closure_controller import ClosureController
from app.controllers.hygiene_controller import HygieneController
from app.models import ClosurePeriod, ClosureReasonType, HawkerCentre, Licensee, SAFEGrade, SafeGradeValue, Stall
from app.rules.engine import Rule, evaluate

TODAY = date(2026, 11, 5)
_rows: list[dict] = []


@pytest.fixture(scope="module", autouse=True)
def _write_results():
    yield
    if path := os.environ.get("LAB4_RESULTS"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_rows, f, indent=1)


def record(section: str, case, actual: str) -> None:
    _rows.append({"section": section, **case.__dict__, "actual": actual, "passed": actual == case.expected})


# ---------------------------------------------------------------------------
# Black box: HygieneController.passes_threshold(stall, threshold)
# ---------------------------------------------------------------------------


@dataclass
class HygieneCase:
    id: str
    classes: str  # which equivalence classes / boundaries it covers
    threshold: str | None  # None = no minimum set
    grades: list[tuple[str, str]]  # (grade, snapshot date), newest first
    last_seen: str | None = "2026-11-01"  # date of the latest SFA export that listed the licence
    licensee: bool = True
    expected: str = ""


def _stall(c: HygieneCase) -> Stall:
    s = Stall(stall_name="Test stall")
    if c.licensee:
        s.licensee = Licensee(
            licence_number="TEST01",
            last_seen_snapshot=date.fromisoformat(c.last_seen) if c.last_seen else None,
            grades=[SAFEGrade(grade_value=SafeGradeValue(g), snapshot_date=date.fromisoformat(d)) for g, d in c.grades],
        )
    return s


SHOWN, HIDDEN = "True (shown)", "False (hidden)"
HYGIENE_CASES = [
    HygieneCase("BB-01", "EC1 no minimum", None, [("C", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-02", "EC1 no minimum, ungraded", None, [], expected=SHOWN),
    HygieneCase("BB-03", "EC2, boundary: grade = minimum", "B", [("B", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-04", "EC2, boundary: one rank above", "B", [("A", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-05", "EC3, boundary: one rank below", "B", [("NEW", "2026-11-01")], expected=HIDDEN),
    HygieneCase("BB-06", "EC3 below minimum", "B", [("C", "2026-11-01")], expected=HIDDEN),
    HygieneCase("BB-07", "EC2, boundary: NEW = minimum (FR-2.2)", "NEW", [("NEW", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-08", "EC3, boundary: C just below NEW", "NEW", [("C", "2026-11-01")], expected=HIDDEN),
    HygieneCase("BB-09", "EC2, boundary: lowest minimum C", "C", [("C", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-10", "EC2, boundary: highest minimum A", "A", [("A", "2026-11-01")], expected=SHOWN),
    HygieneCase("BB-11", "EC3, boundary: just below A", "A", [("B", "2026-11-01")], expected=HIDDEN),
    HygieneCase("BB-12", "EC4 no SAFE grade on record", "C", [], expected=HIDDEN),
    HygieneCase("BB-13", "EC5 no licensee linked", "C", [], licensee=False, expected=HIDDEN),
    HygieneCase("BB-14", "EC2, boundary: snapshot date = last export", "A", [("A", "2026-11-01")], "2026-11-01", expected=SHOWN),
    HygieneCase("BB-15", "EC6, boundary: snapshot 1 day older than last export", "A", [("A", "2026-10-31")], "2026-11-01", expected=HIDDEN),
    HygieneCase("BB-16", "EC2 newest snapshot is the current grade", "B", [("A", "2026-11-01"), ("C", "2026-05-01")], expected=SHOWN),
]


@pytest.mark.parametrize("case", HYGIENE_CASES, ids=lambda c: c.id)
def test_blackbox_passes_threshold(case: HygieneCase):
    threshold = SafeGradeValue(case.threshold) if case.threshold else None
    actual = SHOWN if HygieneController.passes_threshold(_stall(case), threshold) else HIDDEN
    record("blackbox", case, actual)
    assert actual == case.expected


@dataclass
class InvalidThresholdCase:
    id: str
    classes: str
    threshold: str
    expected: str = "HTTP 422 (rejected)"


INVALID_THRESHOLD_CASES = [
    InvalidThresholdCase("BB-17", "EC7 invalid minimum: not a SAFE grade", "D"),
    InvalidThresholdCase("BB-18", "EC7 invalid minimum: lower case", "a"),
]


@pytest.mark.parametrize("case", INVALID_THRESHOLD_CASES, ids=lambda c: c.id)
def test_blackbox_invalid_threshold_is_rejected(client, case: InvalidThresholdCase):
    # The minimum grade reaches HygieneController through the API, which validates it first
    r = client.get("/api/centres", params={"min_grade": case.threshold})
    actual = "HTTP 422 (rejected)" if r.status_code == 422 else f"HTTP {r.status_code}"
    record("blackbox", case, actual)
    assert actual == case.expected


# ---------------------------------------------------------------------------
# White box 1: rules/engine.evaluate(nutrients, rules, conditions)
# Cyclomatic complexity 8 (decisions at nodes 2, 3, 5, 6, 8, 10, 12)
# ---------------------------------------------------------------------------

# The real rules from etl/data/classification_rules.csv that the cases use
RULES = {
    "G-SOD-01": Rule("G-SOD-01", "GENERAL", "sodium_mg", ">", 2000, "mg", "AVOID"),
    "G-SOD-02": Rule("G-SOD-02", "GENERAL", "sodium_mg", ">", 1000, "mg", "MODERATE"),
    "G-KCAL-01": Rule("G-KCAL-01", "GENERAL", "energy_kcal", ">", 700, "kcal", "MODERATE"),
    "DM-SUG-02": Rule("DM-SUG-02", "DIABETES", "sugar_g", ">", 5, "g", "MODERATE"),
}


@dataclass
class EngineCase:
    id: str
    path: str
    rules: list[str]
    nutrients: dict
    conditions: list[str]
    expected: str


ENGINE_CASES = [
    EngineCase("WB1-1", "1-2-3-5-6-7-2-8-10-12-14-15", ["G-SOD-02"], {"sodium_mg": 1200}, [], "MODERATE"),
    EngineCase("WB1-2", "1-2-8-10-12-13-15", [], {"sodium_mg": 1200}, [], "INSUFFICIENT_DATA"),
    EngineCase("WB1-3", "1-2-3-4-2-8-9-8-10-12-13-15", ["G-SOD-02"], {"sodium_mg": None}, [], "INSUFFICIENT_DATA, missing sodium_mg"),
    EngineCase("WB1-4", "1-2-3-5-2-8-10-12-13-15", ["G-SOD-02"], {"sodium_mg": 800}, [], "INSUFFICIENT_DATA"),
    EngineCase(
        "WB1-5", "1-2-3-5-6-7-2-3-5-6-2-8-10-12-14-15", ["G-SOD-02", "G-KCAL-01"], {"sodium_mg": 1200, "energy_kcal": 800}, [], "MODERATE"
    ),
    EngineCase("WB1-6", "1-2-3-5-6-7-2-8-10-11-15", ["G-SOD-01"], {"sodium_mg": 2500}, [], "AVOID"),
    EngineCase(
        "WB1-7",
        "1-2-3-5-6-7-2-3-4-2-8-9-8-10-12-14-15",
        ["G-SOD-02", "G-KCAL-01"],
        {"sodium_mg": 1200, "energy_kcal": None},
        [],
        "MODERATE, missing energy_kcal",
    ),
    EngineCase(
        "WB1-8",
        "1-2-3-5-6-7-2-3-4-2-8-9-8-10-12-13-15",
        ["G-SOD-02", "DM-SUG-02"],
        {"sodium_mg": 1200, "sugar_g": None},
        ["DIABETES"],
        "INSUFFICIENT_DATA, missing sugar_g",
    ),
]


@pytest.mark.parametrize("case", ENGINE_CASES, ids=lambda c: c.id)
def test_whitebox_evaluate(case: EngineCase):
    a = evaluate(case.nutrients, [RULES[r] for r in case.rules], case.conditions)
    actual = a.verdict + (f", missing {', '.join(a.missing_nutrients)}" if a.missing_nutrients else "")
    record("engine", case, actual)
    assert actual == case.expected


# ---------------------------------------------------------------------------
# White box 2: ClosureController.centre_status(centre, today)
# Cyclomatic complexity 4 (decisions at nodes 2, 5, 7)
# ---------------------------------------------------------------------------


@dataclass
class StatusCase:
    id: str
    path: str  # "-" for the extra boundary cases
    nea_status: str
    closures: list[tuple[str, str]]  # (start, end)
    expected: str


STATUS_CASES = [
    StatusCase("WB2-1", "1-2-4-5-7-9-10-11", "Existing", [], "open"),
    StatusCase("WB2-2", "1-2-3-11", "Under Construction", [], "not_operating"),
    StatusCase("WB2-3", "1-2-4-5-6-10-11", "Existing", [("2026-11-04", "2026-11-06")], "closed, reopens 2026-11-07"),
    StatusCase("WB2-4", "1-2-4-5-7-8-10-11", "Existing", [("2026-11-08", "2026-11-09")], "closing_soon, in 3 days"),
    # Boundary values around SOON_DAYS = 7 and the closure's last day (not extra paths)
    StatusCase("WB2-5", "-", "Existing", [("2026-11-12", "2026-11-13")], "closing_soon, in 7 days"),
    StatusCase("WB2-6", "-", "Existing", [("2026-11-13", "2026-11-14")], "open"),
    StatusCase("WB2-7", "-", "Existing", [("2026-11-01", "2026-11-05")], "closed, reopens 2026-11-06"),
    StatusCase("WB2-8", "-", "Existing", [("2026-11-01", "2026-11-04")], "open"),
]


def _centre(c: StatusCase) -> HawkerCentre:
    centre = HawkerCentre(id=1, centre_name="Test centre", region="Central", latitude=1.3, longitude=103.8, nea_status=c.nea_status)
    centre.closures = [
        ClosurePeriod(id=i, start_date=date.fromisoformat(s), end_date=date.fromisoformat(e), reason_type=ClosureReasonType.SPRING_CLEANING)
        for i, (s, e) in enumerate(c.closures, 1)
    ]
    return centre


@pytest.mark.parametrize("case", STATUS_CASES, ids=lambda c: c.id)
def test_whitebox_centre_status(case: StatusCase):
    st = ClosureController.centre_status(_centre(case), TODAY)
    actual = st.state
    if st.state == "closed":
        actual += f", reopens {st.reopens_on}"
    elif st.state == "closing_soon":
        actual += f", in {st.days_to_next} days"
    record("status", case, actual)
    assert actual == case.expected
