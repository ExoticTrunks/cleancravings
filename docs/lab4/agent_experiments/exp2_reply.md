I've ranked five refactorings below and done the top one. I couldn't run anything here, so the test suite hasn't been run yet.

## 1. The five refactorings, ranked

**1. Define each stall-filtering rule once (done, details below).**
- **Why:** the minimum-grade rule (FR-2.5) was written out three times. `HygieneController.passes_threshold` had it, the centre list kept its own grade-number comparison, and the recommendations kept a third copy with a comment saying "Same rule as…". The halal check and the "suspended" flag were each written twice. Your Lab 4 report (`docs/lab4/lab4_test_cases.html:46`) says `passes_threshold()` is what the centre list and recommendations use, but they never called it. So the 16 black-box tests only covered one of the three copies.
- **Risk:** low. Each change swaps code for an equivalent call. The only change in shape is in-memory cached data that nothing outside the controller reads.

**2. Share the centre query and the Cooked Food filter.**
- **Why:** `_centre_query()` and `_cooked()` in `hawker_centre_controller.py` are copied by hand into `recommendation_controller.py:47-62`. The stall loading options are repeated in `search` and `stall_detail`. Also, `centre_detail` and `stall_detail` call `hdp_counts(db)`, which counts every centre in the database just to read one number.
- **Risk:** low. If the shared query loads less up front than the copy did, you'd get many extra database queries (much slower), but the results wouldn't change.

**3. Split up `RecommendationController.recommend` (about 100 lines).**
- **Why:** loading the user's data, the filters, six counters, the scoring weights and the per-centre limit are all in one loop. The scoring is the logic you're most likely to tune, and right now it can't be tested on its own. Pull out a small user-context object, a `_score(...) -> (score, reasons)` function and a `_cap_per_centre` function.
- **Risk:** medium. The order of the reasons, the floating-point sums and the tie-breaks all have to stay exactly the same. Write unit tests that pin the current output before moving anything.

**4. Move business logic out of `routers/public.py`.**
- **Why:** the router works out freshness and staleness, picks the default dish profile, decides the halal default and calls OneMap directly. Your class diagrams describe routers as a thin layer over the controllers. The "SQLite drops the timezone" fix also exists twice (`user_controllers._utc` and an inline copy in `freshness`).
- **Risk:** low to medium. Watch for import cycles. Tests that patch `httpx` will have to patch it in the new module, which means editing tests, so do that step on its own.

**5. Cut the per-row database queries in the ETL scripts.**
- **Why:** `sfa_import.load` runs up to three queries for every row (licensee, stall, grade). That's tens of thousands of round trips per full export against Supabase. Load them all up front into dictionaries. Smaller fixes alongside it: `seed_reference.load` reads the rules CSV twice, and `nea_sync.parse_row` repeats the closure-reason logic.
- **Risk:** medium. Sessions are created with `autoflush=False`, so today a licence that appears twice in one export probably fails when the data is saved. With dictionaries, the second row would quietly update the first instead, which changes behaviour. Add a test for duplicate rows first.

## 2. What I changed (#1)

| File | Change |
|---|---|
| `hygiene_controller.py` | New `grade_passes(grade, threshold)` holds the one copy of the rule. `passes_threshold` now calls it. New `suspended_past_year(licensee)`, also used by `track_record`. |
| `hawker_centre_controller.py` | The cache stores each centre's best grade instead of its grade number. The centre list filter calls `grade_passes`. |
| `recommendation_controller.py` | Uses `grade_passes` and `confirmed_halal` instead of its own copies. The `GRADE_RANK` import is gone. |
| `presenters.py` | Uses `suspended_past_year`. `confirmed_halal` now also accepts a `StallSummary`. |

No tests, API fields or database queries changed.

## How I checked the behaviour is the same

I compared old and new code case by case:

- **`passes_threshold`:** it still returns `True` straight away when no minimum is set, so it doesn't look up the grade in that case, exactly as before. Otherwise it does the same two checks in the same order: no grade means hidden, then grade numbers are compared with `>=`.
- **Centre list:** before, it skipped a centre when `min_grade and best_rank < GRADE_RANK[min_grade]`, where `best_rank` was 0 if the centre had no graded stalls.
  - No minimum set: neither version skips the centre.
  - Minimum set, no graded stalls: old compares `0 < rank`, which is true, so skipped. New: `grade_passes(None, min)` is `False`, so skipped.
  - Minimum set, best grade `g`: each grade has its own distinct number, so the best grade has the highest number and both versions compare `GRADE_RANK[g] >= GRADE_RANK[min]`.
- **Recommendations:** before, it skipped when `threshold and (grade is None or rank < min)`. The minimum is a string enum and never empty, so `threshold` is truthy exactly when it isn't `None`. That makes the old condition the exact opposite of `grade_passes`. `s.halal is not True` is literally `not confirmed_halal(s)`, and the counters still go up on the same branches.
- **Suspended flag:** the same expression, moved into one function.
- **Imports:** I checked the import chain for cycles and confirmed everything is imported where it's used (`SafeGradeValue` was already imported in the centre controller).

Tests that cover these paths: the 16 `test_lab4.py::test_blackbox_passes_threshold` cases, plus the `min_grade`, halal and `excluded_by_hygiene` checks in `test_api.py`.

One gap: no existing test checks which centres `/api/centres?min_grade=…` returns; the only test there just checks a 422 for an invalid grade. That path is the one I reasoned through most carefully above. When you add tests next, one comparing that list against `passes_threshold` on each centre's stalls would cover it.