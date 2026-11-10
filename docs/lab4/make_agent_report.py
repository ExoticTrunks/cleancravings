"""Builds the Lab 4 coding agent report (docs/lab4/coding_agent_report.html).

    python docs/lab4/make_agent_report.py

The prompts, the agent's replies, its code and the test results are read from
docs/lab4/agent_experiments/, saved from the actual runs. Print the HTML to PDF from a browser."""

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE / "agent_experiments"
OUT = HERE / "coding_agent_report.html"
AUTHORS = "Rafael, Albin"

e = html.escape


def inline(s: str) -> str:
    s = e(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def md(text: str) -> str:
    """The Markdown subset the agent's replies use: headings, tables, nested lists, paragraphs."""
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if m := re.match(r"(#{1,4}) (.*)", ln):
            out.append(f"<h5>{inline(m[2])}</h5>")
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            t = "<table class='ai'><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            out.append(t + "</table>")
        elif re.match(r"\s*([-*]|\d+\.) ", ln):
            stack, buf = [], []
            while i < len(lines) and (m := re.match(r"(\s*)([-*]|\d+\.) (.*)", lines[i])):
                depth = len(m[1]) // 2
                tag = "ol" if m[2][0].isdigit() else "ul"
                while len(stack) > depth + 1:
                    buf.append(f"</li></{stack.pop()}>")
                if len(stack) < depth + 1:
                    stack.append(tag)
                    buf.append(f"<{tag}><li>")
                else:
                    buf.append("</li><li>")
                buf.append(inline(m[3]))
                i += 1
                while i < len(lines) and lines[i].strip() == "" and i + 1 < len(lines) and re.match(r"\s*([-*]|\d+\.) ", lines[i + 1]):
                    i += 1
            while stack:
                buf.append(f"</li></{stack.pop()}>")
            out.append("".join(buf))
        elif ln.strip():
            para = [ln]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||\s*([-*]|\d+\.) )", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
        else:
            i += 1
    return "\n".join(out)


def read(name: str) -> str:
    return (EXP / name).read_text(encoding="utf-8").strip()


def prompt(name: str) -> str:
    return "<div class='prompt'>" + "".join(f"<p>{e(p)}</p>" for p in read(name).split("\n\n")) + "</div>"


def reply(name: str) -> str:
    return "<div class='reply'>" + md(read(name)) + "</div>"


def code(name: str) -> str:
    return f"<pre>{e(read(name))}</pre>"


def tests(name: str) -> str:
    return e(read(name).splitlines()[-1].strip())


def build() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Lab 4 Coding Agent Report</title><style>{CSS}</style></head><body>
<section class="cover">
<p class="course">SC2006 Software Engineering</p>
<h1>Lab 4 Deliverables: Coding Agent Report</h1>
<table class="meta">
<tr><td>Lab group</td><td>SCSL, Group 4</td></tr>
<tr><td>Team</td><td>CleanCravings</td></tr>
<tr><td>Members</td><td>Rafael, Albin, Samrithi, Jovan, Jun Ren</td></tr>
<tr><td>Author(s) of this document</td><td>{e(AUTHORS)}</td></tr>
<tr><td>Coding agent</td><td>Claude Code 2.1.306 (Anthropic's coding agent, used from the terminal), model Claude Opus 5.5</td></tr>
<tr><td>Date of the experiments</td><td>5 November 2026</td></tr>
</table>
<h2>Contents</h2>
<ol>
<li>How we ran the experiments</li>
<li>Exercise 3.3.2: regenerating a deleted control class (HygieneController)</li>
<li>Exercise 3.3.3: code quality review and refactoring</li>
<li>Appendix: prompts, the agent's replies, its code and its changes</li>
</ol>
</section>

<section class="pb">
<h2>1. How we ran the experiments</h2>
<p>The lab suggests an in-IDE agent such as Cline. We used <b>Claude Code</b>, a comparable coding agent that reads and edits the
files of a project itself. For each experiment:</p>
<ul>
<li>We exported a <b>fresh copy</b> of our repository into an empty folder and started a <b>new agent session</b> there, so the agent
had no memory of earlier work and could not see our real working copy. We removed <code>CLAUDE.md</code> (our notes for AI tools)
from the copy, because it describes HygieneController's rules in prose and would have given the answer away.</li>
<li>The agent could <b>read, search, create and edit files</b> in the copy, but <b>could not run commands</b>. We ran the test suite
ourselves afterwards, so we could see exactly what it changed and judge it against the same tests we use.</li>
<li>We compared its files with the originals (<code>diff</code>) and ran our full backend test suite (pytest), which includes the
Lab 4 black-box and basis path tests.</li>
</ul>
<p>The exact prompts and the agent's replies are in the appendix. The files it produced are kept in
<code>docs/lab4/agent_experiments/</code> in our repository.</p>

<h2>2. Exercise 3.3.2: regenerating HygieneController</h2>
<h3>What we did</h3>
<p>We chose <b>HygieneController</b>, the control class we black-box tested (section 1 of our Lab 4 test cases). We deleted the
whole file, <code>backend/app/controllers/hygiene_controller.py</code>; with it gone, the test suite could not even start (an
import error during collection). We then gave the agent one prompt (appendix A.1) telling it the file had been deleted and
pointing it to:</p>
<ul>
<li>our tests, especially the Lab 4 black-box tests of <code>passes_threshold</code>;</li>
<li>the code that calls HygieneController;</li>
<li>our design class diagrams and the requirements cited in code comments (FR-2.1 to FR-2.5).</li>
</ul>
<p>We did not give it the original class, not even with the function bodies removed.</p>

<h3>Result</h3>
<table class="facts">
<tr><td>Iterations needed</td><td>None: one prompt, no follow-up</td></tr>
<tr><td>Agent's work</td><td>About 1 minute 45 seconds; 18 file reads and searches, then one file written</td></tr>
<tr><td>Other files changed</td><td>None (checked with <code>diff</code>)</td></tr>
<tr><td>Test suite on its class</td><td><b>{tests("exp1_tests.txt")}</b>, the same as with our original class</td></tr>
</table>
<p>The agent rebuilt the class with the same public interface as ours: the <code>GRADE_RANK</code> ordering A &gt; B &gt; NEW &gt; C
and the four methods <code>current_grade</code>, <code>passes_threshold</code>, <code>summary</code> and <code>track_record</code>,
with the same signatures. It worked these out from the callers and the class diagrams, and the rules from the tests: for
example, that a stall with no current grade fails any minimum, and that a snapshot older than the latest SFA export means
the grade is no longer current. It added docstrings citing the requirements, and sorted the grade history by date instead
of relying on the database's ordering.</p>
<p>Comparing it with our original, line by line, showed <b>two differences in behaviour that none of our tests detected</b>:</p>
<ol>
<li><b><code>summary()</code> counts only Cooked Food stalls</b>; ours counted every stall passed to it. Our SFA import only keeps
Cooked Food stalls (all 5,614 stalls in our data are), so this makes no visible difference today; the agent's version is
the more defensive one (FR-1.6).</li>
<li><b><code>track_record()</code> lists every grade snapshot</b>; ours collapses consecutive identical snapshots so the history shows
only changes. Every licence has one snapshot so far, so the two look the same now, but after a few months of daily SFA imports
the agent's version would show dozens of identical "A" rows on a stall page. This would be a real regression, and our tests
only check that the history is not empty.</li>
</ol>
<p>It also turned our comment "Team to confirm this choice" about where NEW ranks into a settled statement citing FR-2.2.</p>
<p>A second run of the same prompt happened by accident after the first had finished. That session found the agent's own new
file, took it for the original and refused to overwrite it, saying a rewrite after reading it would not be a valid "from
scratch" result (appendix A.3). It did not change anything.</p>

<h3>Reflection</h3>
<p>The outcome exceeded our expectations: the agent rebuilt a working class in one attempt, from tests and diagrams alone, without
seeing the original or running the tests. Its explanation was accurate and traced each decision to a test or a requirement. The
experiment also showed how much it relied on our tests to define "correct": where a behaviour was only in our code and not in
a test or a diagram (collapsing the grade history), it reasonably chose something else, and the suite still passed. The lesson
for us is that our tests are the real specification when an AI writes code, so the gap to close is a test for the collapsed grade
history. Had the agent failed, the next steps we had planned were to paste the test failures back to it, then to give it the
original file with only the function bodies removed.</p>
</section>

<section class="pb">
<h2>3. Exercise 3.3.3: code quality review and refactoring</h2>
<h3>What we did</h3>
<p>Our further experiment was the lab's third suggestion: ask the agent for its opinion on the quality of our codebase, and have it
carry out one of its refactoring suggestions. In a new fresh copy and a new session, we asked it (appendix B.1) to rank the five
refactorings that would most improve the backend, with reasons and risks, then to carry out only the top one without changing
behaviour or tests, and to explain how it made sure behaviour was unchanged.</p>

<h3>Result</h3>
<table class="facts">
<tr><td>Iterations needed</td><td>None: one prompt, no follow-up</td></tr>
<tr><td>Agent's work</td><td>About 3 minutes 10 seconds over 43 steps of reading and editing</td></tr>
<tr><td>Files changed</td><td>4 controller files, 48 changed lines; no tests changed</td></tr>
<tr><td>Test suite before and after</td><td>{tests("exp2_tests.txt")} after, the same as before</td></tr>
<tr><td>Our extra check</td><td>The original and refactored centre list and recommendations give <b>identical results on our real data
in all 15 scenarios we tried</b> (every minimum grade, with and without the halal restriction)</td></tr>
</table>
<p><b>Its five suggestions</b> (in full in appendix B.2):</p>
<ol>
<li>define each stall-filtering rule once;</li>
<li>share the centre query and the Cooked Food filter;</li>
<li>split up the 100-line <code>recommend()</code> method;</li>
<li>move business logic out of the API router;</li>
<li>cut the per-row database queries in the SFA import.</li>
</ol>
<p>Each came with a specific reason and a sensible risk. For example, for number 5 it warned that a licence appearing twice in one
export would behave differently, and said to add a test for that first.</p>
<p><b>The refactoring it carried out</b> (number 1) was well chosen:</p>
<ul>
<li><b>One rule instead of three.</b> Our minimum-grade rule (FR-2.5) was written out in three places: <code>passes_threshold</code>,
the cached centre list and the recommendations. The halal check and the suspension flag were each written twice. It added
<code>HygieneController.grade_passes()</code> and <code>suspended_past_year()</code> and made every caller use them.</li>
<li><b>It caught an error in our own documentation.</b> Our Lab 4 test document says the centre list and recommendations use
<code>passes_threshold()</code>. They had kept their own copies of the rule since we added caching, so our 16 black-box tests only
covered one of the three copies.</li>
<li><b>It named a remaining gap.</b> No test checks which centres the minimum-grade filter returns.</li>
</ul>

<h3>Reflection</h3>
<p>This met and in places exceeded our expectations. The review was specific to our code rather than generic advice, the ranking
was reasonable, and the refactoring was small, safe and easy to check. Its "proof" that behaviour was unchanged was careful
reasoning, not a test run, since it could not run commands; we confirmed it with the test suite and the real-data comparison.
The most valuable result was finding the mismatch between our test document and our code, which a human review had missed. Adopting
this refactoring would make the rule our black-box tests cover the one every list uses, and the missing centre-list test
would close the gap it found. Its suggestions 3 and 5 are medium risk, and we would only attempt them with new tests in place first, as it
advised.</p>
</section>

<section class="pb">
<h2>Appendix</h2>
<h3>A.1 Exercise 3.3.2: our prompt</h3>
{prompt("exp1_prompt.txt")}
<h3>A.2 The agent's reply</h3>
{reply("exp1_reply.md")}
<h3>A.3 The accidental second run's reply</h3>
{reply("exp1_accidental_rerun_reply.md")}
<h3 class="pb">A.4 The class the agent wrote</h3>
{code("exp1_regenerated_hygiene_controller.py")}

<h3 class="pb">B.1 Exercise 3.3.3: our prompt</h3>
{prompt("exp2_prompt.txt")}
<h3>B.2 The agent's reply</h3>
{reply("exp2_reply.md")}
<h3 class="pb">B.3 The changes it made</h3>
<pre class="diff">{e(read("exp2_refactor.diff"))}</pre>
</section>
</body></html>"""


CSS = """
@page { size: A4; margin: 16mm 15mm; @bottom-right { content: "Page " counter(page); font: 9pt Arial, sans-serif; color: #555; }
  @bottom-left { content: "SC2006 SCSL Group 4 | Lab 4 coding agent report"; font: 9pt Arial, sans-serif; color: #555; } }
body { font: 10.3pt/1.45 Arial, Helvetica, sans-serif; color: #111; }
h1 { font-size: 23pt; margin: 6px 0 16px; } h2 { font-size: 14.5pt; margin: 16px 0 6px; border-bottom: 1.5px solid #222; padding-bottom: 2px; }
h3 { font-size: 11.5pt; margin: 12px 0 4px; } h5 { font-size: 10pt; margin: 8px 0 2px; } p { margin: 5px 0; } ul, ol { margin: 4px 0; padding-left: 20px; } li { margin: 2px 0; }
.cover { padding-top: 38mm; } .course { font-size: 13pt; color: #444; margin: 0; }
.meta { border-collapse: collapse; margin: 10px 0 22px; } .meta td { padding: 4px 14px 4px 0; vertical-align: top; } .meta td:first-child { font-weight: bold; }
table.facts { border-collapse: collapse; margin: 6px 0 8px; width: 100%; font-size: 9.5pt; }
table.facts td { border: 1px solid #aaa; padding: 3px 6px; vertical-align: top; } table.facts td:first-child { width: 30%; background: #eef5fb; font-weight: bold; }
code { font: 8.8pt Consolas, monospace; background: #f2f2f2; padding: 0 2px; }
.prompt { background: #f1f1f1; border-left: 3px solid #555; padding: 6px 10px; font: 9pt Consolas, monospace; }
.prompt p { margin: 0 0 6px; white-space: pre-wrap; } .prompt p:last-child { margin: 0; }
.reply { border: 1px solid #bbb; padding: 4px 11px; font-size: 9pt; line-height: 1.4; }
.reply ul, .reply ol { padding-left: 18px; }
table.ai { border-collapse: collapse; width: 100%; margin: 5px 0; font-size: 8.6pt; } table.ai th, table.ai td { border: 1px solid #999; padding: 2px 5px; vertical-align: top; text-align: left; }
table.ai th { background: #e8e8e8; } table.ai tr { break-inside: avoid; }
pre { font: 7.6pt/1.3 Consolas, monospace; background: #fafafa; border: 1px solid #ddd; padding: 6px; white-space: pre-wrap; word-break: break-all; }
.pb { break-before: page; }
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
