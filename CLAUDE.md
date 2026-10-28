# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

CleanCravings (SC2006 SCSL Group 4 prototype): find clean, nearby hawker stalls in Singapore and rate dishes against a user's health conditions, using official SFA (hygiene grades), NEA (centres, closures) and HPB (Healthier Dining) data. FastAPI backend in `backend/`, React 19 + Vite + TypeScript + Tailwind v4 frontend in `frontend/`. See `README.md` for the full requirement-to-code traceability table and open team decisions.

## Commands

Backend (run everything from `backend/`; the ETL modules import `app.*`, so they must be run as `python -m etl.<name>` from that directory). A local venv lives at `backend/.venv` (Windows: `.\.venv\Scripts\Activate.ps1`).

```bash
pip install -r requirements.txt
cp .env.example .env
python -m etl.load_sample          # offline sample data into SQLite (cleancravings.db)
uvicorn app.main:app --reload      # API on :8000, docs at /docs

pytest                             # full suite
pytest tests/test_rules.py         # one file
pytest "tests/test_rules.py::test_rule_boundaries[G-SOD-01]"   # one parametrised case (id = rule_id)
pytest -k closed_centre            # by name
TEST_DATABASE_URL=postgresql://... pytest tests/test_db.py     # RLS check against a real Postgres (only this file)
```

Settings are read once at startup (`get_settings()` is cached) and `--reload` only watches `.py` files, so restart the backend by hand after editing `.env`. A stale process with old auth settings answers "Auth isn't configured on the server". On Windows, check that only one process is listening on :8000, because two can bind the port at once.

Frontend (from `frontend/`; Vite proxies `/api` to `localhost:8000`):

```bash
npm install && cp .env.example .env
npm run dev          # :5173
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + vite build (this is what CI runs)
npm run gen:api      # regenerate src/api/schema.d.ts from the RUNNING backend's /openapi.json
```

`frontend/openapi.json` is a checked-in snapshot of the schema that `gen:api` doesn't touch. Refresh it by hand (one-space JSON indent) when the API changes.

There is no linter configured. CI (`.github/workflows/ci.yml`) runs `pytest -q` and `npm run build`.

## Architecture

### Backend request path

`app/main.py` mounts two routers: `routers/public.py` (`/api/...`, no login) and `routers/me.py` (`/api/me/...`, `require_user`). Routers are thin; logic lives in `app/controllers/*`, which are classes of static/class methods named after the team's control-class design (`HawkerCentreController`, `HygieneController`, `ClosureController`, `HealthierEatingController`, `RecommendationController`, `UserProfileController`, `FavouriteController`, `VisitController`, `AlertController`). `controllers/presenters.py` converts ORM entities into Pydantic response shapes shared across controllers. `app/models.py` (SQLAlchemy 2.0) and `app/schemas.py` (Pydantic) follow the lab 2 class diagram / data dictionary names; deviations are commented in place.

- **No migrations**: `init_db()` calls `create_all` on startup. Schema changes to existing tables need the local DB deleted/reseeded.
- **DB**: SQLite locally, Postgres (Supabase) in prod, chosen by `DATABASE_URL` (plain `postgresql://` is rewritten to psycopg 3). Code must work on both (e.g. SQLite drops tz info on datetimes; see `freshness` in `public.py`). On Postgres, `init_db` also enables RLS with no policies on every table, so Supabase's REST API (anon/authenticated) sees nothing; the backend connects as owner and isn't affected. New tables get it automatically. Don't add policies or `FORCE` without changing how the backend connects. Never run the full suite with `TEST_DATABASE_URL` pointing at a real database, because the `client` fixture loads sample data.
- **"Today"** is always `geo.today_sg()` (Asia/Singapore), passed into controllers explicitly rather than read inside them.
- **Distance** is plain haversine in `app/geo.py` (PostGIS deliberately deferred). Region = nearest of five hardcoded planning-region centroids.

### Auth

Login happens in the browser via Supabase Auth (Google). The backend only verifies the Bearer JWT (`app/auth.py`): HS256 if `SUPABASE_JWT_SECRET` is set, otherwise JWKS from `SUPABASE_URL`. With `DEV_AUTH=true`, tokens of the form `dev:<email>` are accepted. Users are created on first authenticated request. The frontend (`src/lib/auth.tsx`) shows the dev sign-in automatically when `VITE_SUPABASE_*` are blank.

### Data ingestion (ETL), separate from the request path

`backend/etl/` has one module per source, each runnable alone and each wrapped in `common.sync_run(source)`, which logs a `sync_run` row and on failure rolls back so the last good data stays (the API reports staleness from `sync_run` via `/api/meta/freshness`). Every source module exposes a `load(db, rows, ...)` function that both the real sync and `load_sample.py` use, so sample and real data go through the same parsers.

- `seed_reference` → dish profiles and classification rules from `etl/data/*.csv` (source `REF`).
- `nea_sync` → hawker centres + closures from data.gov.sg.
- `sfa_import` → SAFE grades from a manual SFA Excel export dropped into `etl/inbox/` (SFA has no API). Each import appends a dated `SAFEGrade` snapshot per licence; history is built from snapshots and can't be backfilled. Only rows whose postal code matches a hawker centre are kept. The real export has quirks the parser depends on: every cell is OOXML-escaped (`_x0020_` and so on, decoded by `unescape`), there's no postal-code column (it comes from the address), and some centres use bare 3-digit stall numbers instead of `#01-23`.
- `hpb_partners_sync` (HPB Healthier Dining Partners) must run **after** SFA. Hawker rows carry the centre's address, not a stall unit, so outlets are matched to SFA stalls by name (exact, then guarded fuzzy, then centre-level), with manual decisions in `docs/hdp_match_overrides.csv`. `--review` writes `docs/hdp_match_review.csv` without touching the DB. `hpb_sync.py` (Healthier Eateries) is retired and kept only for reference.
- Centre postal-code lookups go through `etl.common.centres_by_postal`, which includes the second code of two-block centres (`Singapore 430013/430014`).
- `run_all` runs them in order, then generates closure alerts. The `etl.yml` workflow runs it daily against Supabase.
- `etl/sample/` is fabricated demo data; closure dates use `{N}` day-offset placeholders resolved relative to today. Runs from it are flagged `is_sample` and the UI shows a "Sample data" banner.

### Halal status

`stall.halal` comes only from HPB's Dining_Concept for stalls linked to an HPB listing. `None` means unknown and must never become `False`; `hpb_partners_sync` resets it each run. The `HALAL` dietary restriction filters stalls, not dishes, keeping only `halal is True` (`presenters.confirmed_halal`) in recommendations and centre stall lists. `/centres/{id}` follows the signed-in user's profile unless `halal_only` is passed. The UI always says that hidden stalls just haven't published a status (`labels.halalNote`).

### Rules as data

Dish verdicts come from `etl/data/classification_rules.csv` (`condition, nutrient, operator, threshold → verdict, citation`), seeded into the `classification_rule` table and evaluated by the generic `app/rules/engine.py`, which knows nothing about specific nutrients. Change thresholds or add rules by editing the CSV (then `python -m etl.seed_reference`), not code. Verdict logic: worst fired rule wins (AVOID > MODERATE > SUITABLE); if any of the user's conditions couldn't be checked due to a missing nutrient, the result is `INSUFFICIENT_DATA` unless something said AVOID. `tests/test_rules.py` generates boundary tests per CSV row, and requires every rule to have a non-empty citation and every (condition, nutrient) band set to cover all values without gaps.

### Hygiene threshold ordering

`HygieneController.GRADE_RANK` ranks A > B > NEW > C. A stall with no current grade (or whose latest snapshot is older than the licensee's `last_seen_snapshot`) fails any minimum-grade filter.

### Frontend

`src/lib/api.ts` is the only HTTP client; its types are aliases into `src/api/schema.d.ts`, generated from the backend's OpenAPI schema. **After changing a backend schema or endpoint, run the backend and `npm run gen:api`**, otherwise the frontend types drift (and the build catches renamed fields). Data fetching in pages uses the `useApi(fn, deps)` hook. App-wide state is in context providers in `src/lib/` (`SettingsProvider`, `AuthProvider`, `LocationProvider`); routes are declared in `src/main.tsx`. The frontend must only talk to our FastAPI backend, never directly to data.gov.sg/SFA/HPB (NFR-5); even geocoding goes through `/api/geocode`. Map is Leaflet with OneMap tiles (Night tiles in dark mode).

TypeScript config is a team decision: `strict: false` but `strictNullChecks: true` and `noUnusedLocals: true`. Don't turn on other strict flags.

### Tests

`tests/conftest.py` points `DATABASE_URL` at a throwaway `tests/.test.db` (or `TEST_DATABASE_URL` to run against Postgres), forces `DEV_AUTH`, and the session-scoped `client` fixture loads the sample data once. API tests assert against that sample dataset (e.g. 15 centres, Amoy closed), so editing `etl/sample/` can break them. Use `AUTH` from conftest for signed-in requests.

## Conventions

- Docstrings and comments cite requirement IDs (FR-x.y, NFR-n, UC-n.0) for traceability; keep doing that when adding behaviour tied to a requirement.
- User-facing wording for verdicts is deliberately soft (Good choice / Have in moderation / Have occasionally / Not enough data, see `src/lib/labels.ts`) so the app doesn't overstate health claims (NFR-6).
