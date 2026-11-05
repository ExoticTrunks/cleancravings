"""Builds the Lab 4 testing deliverable (docs/lab4/lab4_test_cases.html) from a real test run.

    cd backend
    python ../docs/lab4/make_test_report.py

Runs backend/tests/test_lab4.py with LAB4_RESULTS set, so every "Actual Output" in the report is
what the code returned in that run. Print the HTML to PDF from a browser (the page sets A4)."""

import html
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent / "backend"
OUT = HERE / "lab4_test_cases.html"

e = html.escape


def run_tests() -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "results.json"
        env = {**os.environ, "LAB4_RESULTS": str(path)}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_lab4.py"], cwd=BACKEND, env=env, capture_output=True, text=True)
        print(proc.stdout.strip().splitlines()[-1])
        return json.loads(path.read_text(encoding="utf-8"))


def commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "../../backend"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    return (r.stdout.strip() or "unknown") + (" plus uncommitted changes" if dirty else "")


def table(rows: list[dict], inputs, with_path: bool = False, extra: str = "") -> str:
    head = "<tr><th>No.</th>" + ("<th>Basis path</th>" if with_path else "<th>Covers</th>") + "<th>Test Input</th><th>Expected Output</th><th>Actual Output</th><th>Pass?</th></tr>"
    body = ""
    for r in rows:
        second = r["path"] if with_path else r["classes"]
        body += (
            f"<tr><td>{e(r['id'])}</td><td class='small'>{e(second)}</td><td>{inputs(r)}</td>"
            f"<td>{e(r['expected'])}</td><td>{e(r['actual'])}</td><td class='{'pass' if r['passed'] else 'fail'}'>{'Yes' if r['passed'] else 'No'}</td></tr>"
        )
    return f"<table class='tc'>{head}{body}</table>{extra}"


def bb_inputs(r: dict) -> str:
    if "grades" not in r:
        return f"GET /api/centres?min_grade=<code>{e(r['threshold'])}</code>"
    grades = ", ".join(f"{g} ({d})" for g, d in r["grades"]) or "none"
    lic = f"last export: {r['last_seen']}" if r["licensee"] else "no licensee"
    return f"minimum = <code>{e(str(r['threshold']))}</code><br>grades (newest first): {e(grades)}<br>{e(lic)}"


def engine_inputs(r: dict) -> str:
    nutrients = ", ".join(f"{k} = {v}" for k, v in r["nutrients"].items())
    return f"rules: {e(', '.join(r['rules']) or 'none')}<br>nutrients: {e(nutrients)}<br>conditions: {e(', '.join(r['conditions']) or 'none')}"


def status_inputs(r: dict) -> str:
    closures = "; ".join(f"{s} to {t}" for s, t in r["closures"]) or "none"
    return f"nea_status = {e(r['nea_status'])}<br>closures: {e(closures)}<br>today = 2026-11-05"


def build(rows: list[dict]) -> str:
    by = lambda s: [r for r in rows if r["section"] == s]  # noqa: E731
    bb, eng, st = by("blackbox"), by("engine"), by("status")
    passed = sum(r["passed"] for r in rows)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Lab 4 Test Cases</title><style>{CSS}</style></head><body>
<section class="cover">
<p class="course">SC2006 Software Engineering</p>
<h1>Lab 4 Deliverables: Testing</h1>
<table class="meta">
<tr><td>Lab group</td><td>SCSL, Group 4</td></tr>
<tr><td>Team</td><td>CleanCravings</td></tr>
<tr><td>Members</td><td>Rafael, Albin, Samrithi, Jovan, Jun Ren</td></tr>
<tr><td>Author(s) of this document</td><td>Rafael, Albin</td></tr>
<tr><td>Test run</td><td>{date.today().isoformat()}, code at commit {e(commit())}: {passed} of {len(rows)} test cases passed</td></tr>
</table>
<h2>Contents</h2>
<ol class="toc">
<li>Black-box testing: HygieneController
<ol><li>The control class</li><li>Equivalence classes and boundary values</li><li>Test cases and results</li></ol></li>
<li>White-box testing: basis path testing
<ol><li>RuleEngine.evaluate(): control flow graph, basis paths, test cases and results</li>
<li>ClosureController.centre_status(): control flow graph, basis paths, test cases and results</li></ol></li>
<li>How the tests are run</li>
</ol>
</section>

<section class="pb">
<h2>1. Black-box testing: HygieneController</h2>
<h3>1.1 The control class</h3>
<p><b>HygieneController</b> (<code>backend/app/controllers/hygiene_controller.py</code>) holds the food-hygiene logic
(FR-2.1 to FR-2.5). It works out a stall's current SAFE grade from the dated snapshots imported from SFA, builds its
track record, and decides whether a stall meets a user's <i>Hygiene Threshold</i>: the minimum SAFE grade the user
wants to see. That decision, <code>passes_threshold(stall, threshold)</code>, is used by the centre list filter, the
centre page's stall list and the recommendations (FR-2.5, FR-5.4), so it decides which stalls a user is shown.</p>
<p>The rules it implements:</p>
<ul>
<li>Grades are ordered <b>A &gt; B &gt; NEW &gt; C</b>. NEW (a stall licensed less than a year) ranks above C,
because SFA says NEW must not be presented as a failing grade (FR-2.2).</li>
<li>A stall passes if its current grade ranks at or above the minimum. With no minimum set, every stall passes.</li>
<li>The current grade is the newest snapshot. If the licence was in the latest SFA export but its newest grade
snapshot is older than that export, SFA no longer lists a grade for it, so it has no current grade.</li>
<li>A stall with no current grade, or no licensee linked, fails any minimum: the app never shows an ungraded stall
to someone who asked for a minimum grade.</li>
</ul>

<h3>1.2 Equivalence classes and boundary values</h3>
<p><b>Equivalence class testing</b> splits each input's domain into classes the program should treat the same way, and
tests at least one value from each class. <b>Boundary value testing</b> adds the values at and next to the edges of
ordered classes, where off-by-one mistakes happen. SAFE grades are ordered and snapshot dates are ordered, so both
have boundaries.</p>
<p>Inputs: the <b>minimum grade</b> (threshold) and the <b>stall's grade record</b> (its snapshots, the date of the latest
SFA export that listed its licence, and whether a licensee is linked).</p>
<table class="ec">
<tr><th>Class</th><th>Description</th><th>Valid?</th><th>Expected behaviour</th></tr>
<tr><td>EC1</td><td>No minimum set</td><td>Valid</td><td>Shown, whatever the grade</td></tr>
<tr><td>EC2</td><td>Current grade ranks at or above the minimum</td><td>Valid</td><td>Shown</td></tr>
<tr><td>EC3</td><td>Current grade ranks below the minimum</td><td>Valid</td><td>Hidden</td></tr>
<tr><td>EC4</td><td>Minimum set, stall has no SAFE grade on record</td><td>Valid</td><td>Hidden</td></tr>
<tr><td>EC5</td><td>Minimum set, no licensee linked to the stall</td><td>Valid</td><td>Hidden</td></tr>
<tr><td>EC6</td><td>Newest snapshot older than the latest export listing the licence (grade no longer listed)</td><td>Valid</td><td>Hidden</td></tr>
<tr><td>EC7</td><td>Minimum is not one of A, B, NEW, C (e.g. "D", "a")</td><td>Invalid</td><td>Rejected by the API (HTTP 422)</td></tr>
</table>
<p><b>Boundary values.</b> Ranks: A = 4, B = 3, NEW = 2, C = 1. For a minimum <i>m</i> the boundaries are a grade one rank
below <i>m</i>, equal to <i>m</i> and one rank above <i>m</i>; the lowest (C) and highest (A) minimums are tested at
their edges. For EC6 the boundary is the snapshot date: equal to the last export date (still current) versus one day
older (no longer current).</p>
<table class="ec">
<tr><th>Minimum</th><th>One rank below</th><th>At the minimum</th><th>One rank above</th></tr>
<tr><td>A</td><td>B: hidden (BB-11)</td><td>A: shown (BB-10)</td><td>none</td></tr>
<tr><td>B</td><td>NEW: hidden (BB-05)</td><td>B: shown (BB-03)</td><td>A: shown (BB-04)</td></tr>
<tr><td>NEW</td><td>C: hidden (BB-08)</td><td>NEW: shown (BB-07)</td><td>covered by B and A rows</td></tr>
<tr><td>C</td><td>none</td><td>C: shown (BB-09)</td><td>covered by NEW rows</td></tr>
</table>

<h3>1.3 Test cases and results</h3>
<p>Method under test: <code>HygieneController.passes_threshold(stall, threshold)</code>. "Shown" means it returned
<code>True</code>. Snapshot and export dates are in 2026. BB-17 and BB-18 go through the API, which validates the
minimum before it reaches the controller.</p>
{table(bb, bb_inputs)}
</section>

<section class="pb">
<h2>2. White-box testing: basis path testing</h2>
<p>For each method we drew the control flow graph, worked out its cyclomatic complexity
<i>V(G)</i> = number of decision points + 1 (checked with <i>E</i> − <i>N</i> + 2), and chose a basis set of
<i>V(G)</i> independent paths: a baseline path, then one path for each decision with that decision's outcome flipped.
Each path has one test case. Node numbers in the paths match the graphs.</p>

<h3>2.1 RuleEngine.evaluate(nutrients, rules, conditions)</h3>
<p><code>backend/app/rules/engine.py</code> decides a dish's verdict for a user's health conditions from the
classification rules (rules as data). The worst verdict among the rules that fire wins (AVOID &gt; MODERATE &gt;
SUITABLE). If a condition the user has could not be checked because the dish lacks that nutrient, the result is
INSUFFICIENT_DATA unless a rule already said AVOID (NFR-6: never guess).</p>
<div class="cfg"><img src="CFG_evaluate.png" alt="Control flow graph of evaluate()"></div>
<p class="small">If the image is unclear, see <code>CFG_evaluate.png</code> uploaded with this document.</p>
<p><b>Cyclomatic complexity.</b> Decision points: nodes 2, 3, 5, 6, 8, 10 and 12 (7 decisions), so
<i>V(G)</i> = 7 + 1 = <b>8</b>. Check: 21 edges and 15 nodes, so 21 − 15 + 2 = 8.</p>
<p><b>Basis paths.</b> P1 is the baseline; each later path flips one decision of the baseline:</p>
<ol class="paths">
<li>Baseline: one rule, value present, rule fires, verdict MODERATE: 1-2-3-5-6-7-2-8-10-12-14-15</li>
<li>Decision 2 false at once (no applicable rules): 1-2-8-10-12-13-15</li>
<li>Decision 3 true (nutrient missing), which also makes decision 8 true: 1-2-3-4-2-8-9-8-10-12-13-15</li>
<li>Decision 5 false (rule does not fire): 1-2-3-5-2-8-10-12-13-15</li>
<li>Decision 6 false (second verdict not worse than the first): 1-2-3-5-6-7-2-3-5-6-2-8-10-12-14-15</li>
<li>Decision 10 true (a rule said AVOID): 1-2-3-5-6-7-2-8-10-11-15</li>
<li>Decision 8 true while the condition was still checked by another rule: 1-2-3-5-6-7-2-3-4-2-8-9-8-10-12-14-15</li>
<li>Decision 12 true although a rule fired (a user's condition could not be checked): 1-2-3-5-6-7-2-3-4-2-8-9-8-10-12-13-15</li>
</ol>
<p class="small">The rules in the inputs are the real rows from <code>classification_rules.csv</code>: G-SOD-01 (sodium &gt; 2000 mg: AVOID),
G-SOD-02 (sodium &gt; 1000 mg: MODERATE), G-KCAL-01 (energy &gt; 700 kcal: MODERATE), DM-SUG-02 (diabetes, sugar &gt; 5 g: MODERATE).</p>
{table(eng, engine_inputs, with_path=True)}

<h3 class="pb">2.2 ClosureController.centre_status(centre, today)</h3>
<p><code>backend/app/controllers/closure_controller.py</code> decides whether a hawker centre is open, closing soon (a
closure starts within 7 days), closed today, or no longer operating (FR-3.2). The status drives the badges on every
centre card, the "closed today" banner and the exclusion of closed centres from recommendations (FR-3.3).</p>
<div class="cfg"><img src="CFG_centre_status.png" alt="Control flow graph of centre_status()"></div>
<p class="small">If the image is unclear, see <code>CFG_centre_status.png</code> uploaded with this document.
Node 4 finds the first matching closures with Python's <code>next()</code>, treated as a single statement here.</p>
<p><b>Cyclomatic complexity.</b> Decision points: nodes 2, 5 and 7 (3 decisions), so <i>V(G)</i> = 3 + 1 = <b>4</b>.
Check: 13 edges and 11 nodes, so 13 − 11 + 2 = 4.</p>
<ol class="paths">
<li>Baseline (open, no closures): 1-2-4-5-7-9-10-11</li>
<li>Decision 2 true (not operating): 1-2-3-11</li>
<li>Decision 5 true (closed today): 1-2-4-5-6-10-11</li>
<li>Decision 7 true (closing soon): 1-2-4-5-7-8-10-11</li>
</ol>
{table(st, status_inputs, with_path=True, extra="<p class='small'>WB2-5 to WB2-8 are extra boundary-value cases on the same paths: a closure starting in exactly 7 days versus 8 days, and one ending today versus yesterday.</p>")}
</section>

<section>
<h2>3. How the tests are run</h2>
<p>Every test case above is an automated pytest test in <code>backend/tests/test_lab4.py</code>, run in CI on every push
with the rest of the suite. This document is generated from a real run by <code>docs/lab4/make_test_report.py</code>,
so the Actual Output column is what the code returned. To re-run: <code>cd backend</code>, then
<code>pytest tests/test_lab4.py -v</code>.</p>
</section>
</body></html>"""


CSS = """
@page { size: A4; margin: 18mm 16mm; @bottom-right { content: "Page " counter(page); font: 9pt Arial, sans-serif; color: #555; }
  @bottom-left { content: "SC2006 SCSL Group 4 | Lab 4 Testing"; font: 9pt Arial, sans-serif; color: #555; } }
body { font: 10.5pt/1.45 Arial, Helvetica, sans-serif; color: #111; }
h1 { font-size: 24pt; margin: 6px 0 18px; } h2 { font-size: 15pt; margin: 18px 0 6px; border-bottom: 1.5px solid #222; padding-bottom: 2px; }
h3 { font-size: 12pt; margin: 14px 0 4px; } p { margin: 5px 0; } ul, ol { margin: 4px 0; padding-left: 22px; }
.cover { padding-top: 40mm; } .course { font-size: 13pt; color: #444; margin: 0; }
.meta { border-collapse: collapse; margin: 10px 0 24px; } .meta td { padding: 4px 14px 4px 0; vertical-align: top; } .meta td:first-child { font-weight: bold; }
.toc li { margin: 3px 0; }
code { font: 9pt Consolas, monospace; background: #f2f2f2; padding: 0 2px; }
table.tc, table.ec { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; }
table.tc th, table.tc td, table.ec th, table.ec td { border: 1px solid #888; padding: 3px 5px; vertical-align: top; text-align: left; }
table.tc th, table.ec th { background: #dcecf7; } table.tc td:first-child { white-space: nowrap; } table.tc tr, table.ec tr { break-inside: avoid; }
td.pass { color: #126b2a; font-weight: bold; } td.fail { color: #b00020; font-weight: bold; }
.small { font-size: 8.5pt; color: #444; } .paths li { margin: 2px 0; font-size: 9.5pt; }
.cfg { text-align: center; margin: 6px 0; break-inside: avoid; } .cfg img { max-width: 100%; max-height: 165mm; }
.pb { break-before: page; }
"""


if __name__ == "__main__":
    rows = run_tests()
    OUT.write_text(build(rows), encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({sum(r['passed'] for r in rows)}/{len(rows)} passed)")
