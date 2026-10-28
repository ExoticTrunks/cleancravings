"""Scheduled entry point (GitHub Actions cron). Each source runs independently, so one
outage doesn't block the others (NFR-10). SFA is imported only if an export has been
dropped into etl/inbox/.

    python -m etl.run_all
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.db import SessionLocal
from app.geo import today_sg
from app.controllers.closure_controller import ClosureController

# hpb_sync (HPB "Healthier Eateries") is retired: mostly chain outlets, almost no hawker stalls.
# The file is kept for reference; hpb_partners_sync replaces it.
from . import hpb_partners_sync, nea_sync, seed_reference, sfa_import

INBOX = Path(__file__).parent / "inbox"


def main() -> int:
    failures = 0
    steps = [("REF", seed_reference.main), ("NEA", nea_sync.main)]
    exports = sorted(p for p in INBOX.glob("*") if p.suffix.lower() in (".xlsx", ".csv") and "suspended" not in p.name)
    if exports:
        susp = next((p for p in INBOX.glob("*suspended*")), None)
        args = [str(exports[-1])] + (["--suspended", str(susp)] if susp else [])
        steps.append(("SFA", lambda: sfa_import.main(args)))
    else:
        print("[SFA] no export in etl/inbox/, skipping (see etl/sfa_import.py)")
    steps.append(("HPB", lambda: hpb_partners_sync.main([])))  # after SFA: outlets are matched to SFA stalls by name

    for name, fn in steps:
        try:
            fn()
        except Exception:  # noqa: BLE001  (already logged to sync_run)
            failures += 1
            print(f"[{name}] failed, keeping last good data", file=sys.stderr)

    db = SessionLocal()
    try:
        print(f"[alerts] created {ClosureController.generate_alerts(db, today_sg())} closure alerts")
    finally:
        db.close()
    return 1 if failures == len(steps) else 0


if __name__ == "__main__":
    raise SystemExit(main())
