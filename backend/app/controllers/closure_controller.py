"""ClosureController (FR-3.1 to FR-3.4)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ClosureAlert, ClosurePeriod, ClosureReasonType, Favourite, FavouriteTarget, HawkerCentre
from ..schemas import CentreStatus, ClosureOut

REASON_LABEL = {
    ClosureReasonType.SPRING_CLEANING: "Spring Cleaning",
    ClosureReasonType.REPAIRS_AND_REDECORATION: "Repairs & Redecoration",
    ClosureReasonType.OTHER_WORKS: "Other Works",
}
SOON_DAYS = 7


class ClosureController:
    @staticmethod
    def centre_status(centre: HawkerCentre, today: date) -> CentreStatus:
        if centre.nea_status and "existing" not in centre.nea_status.lower():
            return CentreStatus(state="not_operating")
        active = next((c for c in centre.closures if c.is_active(today)), None)
        upcoming = next((c for c in centre.closures if c.start_date > today), None)
        days_to_next = (upcoming.start_date - today).days if upcoming else None
        if active:
            state = "closed"
        elif upcoming and days_to_next is not None and days_to_next <= SOON_DAYS:
            state = "closing_soon"
        else:
            state = "open"
        return CentreStatus(
            state=state,
            active_closure=ClosureOut.model_validate(active) if active else None,
            next_closure=ClosureOut.model_validate(upcoming) if upcoming else None,
            days_to_next=days_to_next,
            reopens_on=active.end_date + timedelta(days=1) if active else None,
        )

    @staticmethod
    def closed_centre_ids(db: Session, today: date) -> set[int]:
        rows = db.scalars(
            select(ClosurePeriod.centre_id).where(ClosurePeriod.start_date <= today, ClosurePeriod.end_date >= today)
        )
        return set(rows)

    @staticmethod
    def generate_alerts(db: Session, today: date) -> int:
        """Create a ClosureAlert for each user whose favourite centre has a closure that is
        active or starts within the alert window. Idempotent (unique per user+closure).
        Only favourited centres get alerts (UC-8.0 special requirement)."""
        horizon = today + timedelta(days=get_settings().closure_alert_days)
        favs = db.scalars(select(Favourite).where(Favourite.target_type == FavouriteTarget.CENTRE)).all()
        if not favs:
            return 0
        existing = {(u, c) for u, c in db.execute(select(ClosureAlert.user_id, ClosureAlert.closure_id))}
        created = 0
        for fav in favs:
            closures = db.scalars(
                select(ClosurePeriod).where(
                    ClosurePeriod.centre_id == fav.target_id,
                    ClosurePeriod.end_date >= today,
                    ClosurePeriod.start_date <= horizon,
                )
            ).all()
            for c in closures:
                if (fav.user_id, c.id) in existing:
                    continue
                centre = c.centre
                when = (
                    f"is closed until {c.end_date:%d %b}"
                    if c.is_active(today)
                    else f"will be closed from {c.start_date:%d %b} to {c.end_date:%d %b}"
                )
                db.add(
                    ClosureAlert(
                        user_id=fav.user_id,
                        closure_id=c.id,
                        message=f"{centre.centre_name} {when} for {REASON_LABEL[c.reason_type]}.",
                    )
                )
                existing.add((fav.user_id, c.id))
                created += 1
        db.commit()
        return created
