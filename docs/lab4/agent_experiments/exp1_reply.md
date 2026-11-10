I've recreated `backend/app/controllers/hygiene_controller.py` and changed no other file. I couldn't run the tests because there's no shell in this session. I checked the file by hand against all 16 black-box cases in `test_lab4.py` and against `test_etl.py`, `test_api.py` and the three callers. Run `pytest` in `backend/` to confirm.

**What the class provides.** The callers and both class diagrams use a module-level `GRADE_RANK` and four static methods: `current_grade`, `passes_threshold`, `summary` and `track_record`. The class has those and nothing more.

**Design decisions:**

1. **Grade order A=4, B=3, NEW=2, C=1 (FR-2.2).** NEW sits above C so it never looks like a failing grade, which tests BB-07 and BB-08 check. All ranks are above 0 because `HawkerCentreController._cached_summaries` uses `default=0` to mean "no graded stall".

2. **`current_grade(licensee)` (FR-2.1).** It takes the newest snapshot, sorted by date. It doesn't rely on the database's ordering because the Lab 4 tests build objects in memory. If that snapshot is older than `last_seen_snapshot`, it returns `None`: the latest SFA export listed the licence without a grade, such as "Not Under SAFE". Tests BB-14, BB-15 and the ETL "Not Under SAFE" test cover this.

3. **`passes_threshold(stall, threshold)` (FR-2.5, FR-5.4).** With no minimum set, every stall passes. With a minimum, a stall passes only if its grade ranks at or above it. A stall with no current grade or no linked licensee fails. This matches the rule `RecommendationController` already copies inline. Invalid minimums such as "D" or "a" are rejected by the API (HTTP 422) before they reach this method, so it doesn't check for them.

4. **`summary(stalls)`.** It counts only Cooked Food stalls (FR-1.6), because `presenters.centre_summary` passes it all of a centre's stalls. Stalls with no current grade are counted as `ungraded`.

5. **`track_record(stall)` (FR-2.3, FR-2.4).** It's built from the snapshots rather than stored, as the entity diagram notes.
   - **Suspended flag:** it comes from `licence_status`, which is what the ETL test needs and what `stall_summary` uses. The grade row can't be used because a "Not Under SAFE" export creates no grade row.
   - **Last updated:** this is the date of the latest SFA export that listed the licence.
   - **Grade history:** all grades, newest first.
   - **Demerit points:** this stays null because SFA doesn't publish them.
   - **No licensee:** it returns an empty record instead of failing.