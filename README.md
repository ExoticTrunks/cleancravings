# CleanCravings: prototype v0.2

SC2006 SCSL Group 4. Find clean, nearby hawker stalls and get simple dish ratings for your health needs, using official SFA, NEA and HPB data.

This version follows the team's lab 2 materials: the stack from the AI tech stack evaluation (section 7 decisions), entity names from the class diagram and data dictionary, controllers from the key boundary/control classes doc, and screens from the dialog map.

## Stack (as decided in the tech stack evaluation)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 19 + Vite + **TypeScript** + Tailwind v4 | `strictNullChecks` on, other strict options off (team decision) |
| Map | Leaflet + **OneMap** tiles (SLA) | Default tiles in light mode, Night tiles in dark mode |
| Backend | **FastAPI** (Python) | All data reaches the client through our own API (NFR-5) |
| Database | **PostgreSQL on Supabase** | SQLite is used locally so no one needs Supabase to start |
| Distance | Plain haversine in Python | PostGIS deferred, as the team decided |
| Auth | **Supabase Auth** (Google sign-in) | Backend verifies the JWT. Dev sign-in when Supabase isn't set up |
| Data ingestion | Python ETL scripts + **GitHub Actions cron** | Separate from the request path |
| Testing | **pytest, parametrised over the rule table** | One test per rule, generated from the CSV |
| Diagrams | PlantUML | `docs/diagrams/` (use case, entity and design class diagrams, dialog map, architecture) |

## Run it locally

Needs Python 3.11+ and Node 20+.

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m etl.load_sample          # offline demo data (or see "Real data" below)
uvicorn app.main:app --reload      # http://localhost:8000/docs for the API

# 2. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                        # http://localhost:5173
```

Without Supabase keys, the sign-in page shows a **dev sign-in** (type any email). That's for testing only.

Tests: `cd backend && pytest` (87 tests). Type check: `cd frontend && npm run typecheck`.

## Real data

| Source | Dataset | Script | What we take |
|---|---|---|---|
| NEA | [Dates of Hawker Centres Closure](https://data.gov.sg/datasets/d_bda4baa634dd1cc7a6c7cad5f19e2d68/view) (`d_bda4baa634dd1cc7a6c7cad5f19e2d68`) | `etl/nea_sync.py` | 123 hawker centres, locations, closure dates |
| SFA | [Track Records](https://www.sfa.gov.sg/tools-and-resources/track-records) "Export to Excel" (no API) | `etl/sfa_import.py` | Stalls, SAFE grades, suspensions. Every NEA-managed stall in the export matches a centre |
| HPB | [Healthier Dining Partners - F&B Partners](https://data.gov.sg/datasets/d_c475b9170c08f90580f4041bffd51639/view) (`d_c475b9170c08f90580f4041bffd51639`) | `etl/hpb_partners_sync.py` | Hawker stalls in the Healthier Dining Programme, their endorsement criteria and halal status |
| Team | `etl/data/*.csv` | `etl/seed_reference.py` | Dish profiles and classification rules |

HPB's older "Healthier Eateries" layer (`etl/hpb_sync.py`) is retired. It's mostly chain outlets and placed only 16 outlets at hawker centres, none at a known stall. The file is kept for reference.

```bash
cd backend
python -m etl.seed_reference   # dish profiles + classification rules from etl/data/*.csv
python -m etl.nea_sync         # 123 hawker centres + closure dates (data.gov.sg)
python -m etl.sfa_import etl/inbox/<export>.xlsx [--suspended etl/inbox/<suspended>.xlsx]
python -m etl.hpb_partners_sync --review   # optional: write docs/hdp_match_review.csv, no DB writes
python -m etl.hpb_partners_sync            # Healthier Dining stalls (data.gov.sg), run after SFA
```

- **HPB stalls are matched by name.** The partners list gives each hawker stall its centre's address, not its own unit, so each outlet is placed at a centre by postal code and then matched to an SFA stall there by name. Exact means the names are the same after ignoring case, punctuation and company suffixes. Fuzzy means a similarity of at least 0.90, clearly ahead of the next candidate, with the name minus generic dish words also agreeing. Anything else stays at centre level ("Also in the Healthier Dining Programme"). To fix a wrong or missed match, add a row to `docs/hdp_match_overrides.csv` (`accept` or `reject` an outlet/stall pair). Overrides beat the algorithm.

- **SFA has no API.** SAFE grades come from the "Export to Excel" button on [SFA Track Records](https://www.sfa.gov.sg/tools-and-resources/track-records). Someone needs to export it and drop the file in `backend/etl/inbox/`. Only rows whose postal code matches a hawker centre are kept. **Each import adds a dated snapshot**, and grade history is built from those snapshots. History can't be backfilled, so start doing this regularly now.
- For suspensions, do a second export with "Licence Suspended in the past 1 year" ticked and pass it as `--suspended`.
- `python -m etl.run_all` runs everything. The GitHub Action (`.github/workflows/etl.yml`) runs it every day at 2am SGT against Supabase. Add a `DATABASE_URL` repo secret first.
- If a sync fails, the last good data stays in place, and the app shows "last updated" and stale warnings (NFR-2, NFR-9).

### Switching to Supabase

1. Create a project in the Singapore region. Copy the **pooled** Postgres connection string into `backend/.env` as `DATABASE_URL=postgresql+psycopg://...`.
2. Set `SUPABASE_URL` in `backend/.env` and set `DEV_AUTH=false`.
3. Enable the Google provider under Authentication. Put `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `frontend/.env`.
4. Run the ETL once against it.

On Postgres, the backend turns on row-level security (with no policies) for every table at startup and on every ETL run. Supabase's public REST API therefore can't read any of our tables with the anon key, while the backend connects as the tables' owner and works as before. To check against a database: `TEST_DATABASE_URL=postgresql://... pytest tests/test_db.py` (only that file: the full suite loads sample data).

## Rules as data

`backend/etl/data/classification_rules.csv` holds every rule as `nutrient + operator + threshold → verdict + citation`. One generic evaluator (`app/rules/engine.py`) runs them all. To change a threshold or add a condition, edit the CSV and run `python -m etl.seed_reference`; no Python needed. Every new row gets its own boundary tests automatically (`tests/test_rules.py`).

How a verdict is reached: the worst fired rule wins (AVOID > MODERATE > SUITABLE). If one of the user's conditions can't be checked because a nutrient value is missing, the result is `INSUFFICIENT_DATA` unless something already said AVOID. The UI uses softer wording (Good choice / Have in moderation / Have occasionally / Not enough data) so it doesn't overstate things (NFR-6).

## What's where (traceability)

| Requirement / UC | Screen (boundary) | Backend control class |
|---|---|---|
| FR-1.1–1.4, UC-2.0 | Finder & Map (`pages/Finder.tsx`) | `HawkerCentreController` |
| FR-1.5–1.7 | Centre + stall pages | `StallController` |
| FR-2.1–2.5 | Stall page, grade filters | `HygieneController` |
| FR-3.1–3.4, UC-8.0 | Centre page, Alerts | `ClosureController` |
| FR-4.1, 4.4 | Stall page, HDP badges | `HealthierEatingController` |
| UC-6.0 | Dishes | `HealthierEatingController` + rule engine |
| FR-5.1–5.5, UC-1.0 | Setup / Edit preferences | `UserProfileController` |
| FR-5.6, FR-5.9 | Home "for you" | `RecommendationController` |
| FR-5.7, UC-7.0 | Bookmark buttons, Saved | `FavouriteController` |
| FR-5.8, UC-4.0 | Log a visit, Profile | `VisitController` |
| UC-10.0 | Profile → Accessibility | (client only) |
| NFR-2, 9, 10 | Data sources banner | `etl/*_sync.py`, `sync_run` table |

## Decisions the team should confirm

- **Rule thresholds are drafts.** Only the 2,000 mg/day sodium limit is HPB's own figure. The per-meal cut-offs, sugar and saturated fat rules are placeholders marked `TBC` in the CSV.
- **Dish data:** sodium and protein for 41 dishes come from KKH Dept of Nutrition & Dietetics figures (via SingHealth HealthXchange, compiled on a third-party site). Energy, sugar and saturated fat are empty, so diabetes and cholesterol ratings show "Not enough data" for now. Replace with SG FoodID values.
- **NEW in the hygiene threshold** is ranked between B and C (A > B > NEW > C).
- **Region** is the nearest of five planning-region centre points, which is approximate. URA's region boundary layer would be exact.
- **Halal:** the "No pork / No beef / Vegetarian" filters use typical recipes. Stalls in the Healthier Dining Programme carry HPB's Halal / Non-Halal label (`stall.halal`, unknown for every other stall). The stall page shows it, and the **Halal** restriction in the profile keeps only confirmed-halal stalls in recommendations and centre stall lists, with a note that most stalls haven't published a status. It's HPB's dining-concept label, not MUIS certification, and it doesn't filter dishes.
- **Not built yet:** cuisine, price, opening hours and contact details (no open dataset has them), so the budget filter is saved but unused. Also not built: OneMap routing (UC-2.1 uses "Open in Maps" for now), push notifications (alerts are in-app), the weekly digest and PDF export (UC-4.1, 4.2), community reports (UC-9.0) and ratings/comments (UC-11.0).
- Demerit points per licensee aren't published by SFA, so the track record shows the suspension flag and grade history instead.

## Sample data

`backend/etl/sample/` is **made up** for offline demos: real centre names and approximate locations, but fake stalls, grades and closure dates (relative to today). The app shows a "Sample data" banner whenever any source came from it.
