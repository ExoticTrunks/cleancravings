"""UserProfileController (FR-5.1 to 5.5), FavouriteController (FR-5.7, UC-7.0),
VisitController (FR-5.8, UC-4.0) and the alert inbox side of FR-3.4."""

from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..geo import REGIONS
from ..models import (
    ClosureAlert,
    DishType,
    Favourite,
    FavouriteTarget,
    HawkerCentre,
    Stall,
    User,
    UserProfile,
    Visit,
)
from ..schemas import AlertOut, ClosureOut, FavouriteIn, FavouriteOut, ProfileIn, ProfileOut, VisitIn, VisitOut
from .closure_controller import ClosureController


def _utc(dt: datetime) -> datetime:
    # SQLite hands back naive datetimes; we always store UTC
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class UserProfileController:
    @staticmethod
    def get(db: Session, user: User) -> ProfileOut | None:
        p = db.get(UserProfile, user.id)
        return ProfileOut.model_validate(p, from_attributes=True) if p else None

    @staticmethod
    def save(db: Session, user: User, data: ProfileIn) -> ProfileOut:
        if data.budget_min is not None and data.budget_max is not None and data.budget_min > data.budget_max:
            raise HTTPException(422, "Budget minimum can't be more than the maximum")
        bad = [r for r in data.preferred_regions if r not in REGIONS]
        if bad:
            raise HTTPException(422, f"Unknown region(s): {', '.join(bad)}")
        p = db.get(UserProfile, user.id) or UserProfile(user_id=user.id)
        for k, v in data.model_dump().items():
            setattr(p, k, v)
        db.add(p)
        db.commit()
        db.refresh(p)
        return ProfileOut.model_validate(p, from_attributes=True)


class FavouriteController:
    @staticmethod
    def _describe(db: Session, f: Favourite, today: date) -> FavouriteOut:
        label, subtitle, unavailable, status = "Unavailable", None, True, None
        if f.target_type == FavouriteTarget.CENTRE and (c := db.get(HawkerCentre, f.target_id)):
            label, subtitle, unavailable = c.centre_name, c.region, False
            status = ClosureController.centre_status(c, today)
        elif f.target_type == FavouriteTarget.STALL and (s := db.get(Stall, f.target_id)):
            label, subtitle, unavailable = s.stall_name, s.centre.centre_name, False
            status = ClosureController.centre_status(s.centre, today)
        elif f.target_type == FavouriteTarget.DISH and (d := db.get(DishType, f.target_id)):
            label, subtitle, unavailable = d.dish_name, d.category, False
        return FavouriteOut(
            id=f.id,
            target_type=f.target_type,
            target_id=f.target_id,
            date_saved=_utc(f.date_saved),
            label=label,
            subtitle=subtitle,
            unavailable=unavailable,  # UC-7.0 EX.2, e.g. centre dropped from NEA list
            centre_status=status,
        )

    @classmethod
    def list(cls, db: Session, user: User, today: date) -> list[FavouriteOut]:
        favs = db.scalars(select(Favourite).where(Favourite.user_id == user.id).order_by(Favourite.date_saved.desc()))
        return [cls._describe(db, f, today) for f in favs]

    @classmethod
    def add(cls, db: Session, user: User, data: FavouriteIn, today: date) -> FavouriteOut:
        model = {FavouriteTarget.CENTRE: HawkerCentre, FavouriteTarget.STALL: Stall, FavouriteTarget.DISH: DishType}
        if db.get(model[data.target_type], data.target_id) is None:
            raise HTTPException(404, "Nothing to bookmark with that id")
        existing = db.scalars(
            select(Favourite).where(
                Favourite.user_id == user.id,
                Favourite.target_type == data.target_type,
                Favourite.target_id == data.target_id,
            )
        ).first()
        f = existing or Favourite(user_id=user.id, target_type=data.target_type, target_id=data.target_id)
        db.add(f)
        db.commit()
        if data.target_type == FavouriteTarget.CENTRE:
            ClosureController.generate_alerts(db, today)  # warn straight away if it's about to close
        return cls._describe(db, f, today)

    @staticmethod
    def remove(db: Session, user: User, fav_id: int) -> None:
        f = db.get(Favourite, fav_id)
        if f is None or f.user_id != user.id:
            raise HTTPException(404, "Bookmark not found")
        db.delete(f)
        db.commit()


class VisitController:
    @staticmethod
    def _out(v: Visit, db: Session) -> VisitOut:
        s = db.get(Stall, v.stall_id)
        d = db.get(DishType, v.dish_type_id) if v.dish_type_id else None
        return VisitOut(
            id=v.id,
            stall_id=v.stall_id,
            stall_name=s.stall_name if s else "Removed stall",
            centre_name=s.centre.centre_name if s else "",
            dish_name=d.dish_name if d else None,
            visit_date=v.visit_date,
            rating=v.rating,
            note=v.note,
        )

    @classmethod
    def add(cls, db: Session, user: User, data: VisitIn, today: date) -> VisitOut:
        if db.get(Stall, data.stall_id) is None:
            raise HTTPException(404, "Stall not found")
        if data.visit_date and data.visit_date > today:
            raise HTTPException(422, "Visit date can't be in the future")
        v = Visit(user_id=user.id, **{**data.model_dump(), "visit_date": data.visit_date or today})
        db.add(v)
        db.commit()
        return cls._out(v, db)

    @classmethod
    def list(cls, db: Session, user: User) -> list[VisitOut]:
        rows = db.scalars(select(Visit).where(Visit.user_id == user.id).order_by(Visit.visit_date.desc(), Visit.id.desc()))
        return [cls._out(v, db) for v in rows]


class AlertController:
    @staticmethod
    def list(db: Session, user: User, today: date) -> list[AlertOut]:
        ClosureController.generate_alerts(db, today)
        rows = db.scalars(
            select(ClosureAlert).where(ClosureAlert.user_id == user.id).order_by(ClosureAlert.sent_timestamp.desc())
        ).all()
        return [
            AlertOut(
                id=a.id,
                message=a.message,
                sent_timestamp=_utc(a.sent_timestamp),
                read_status=a.read_status,
                centre_id=a.closure.centre_id,
                closure=ClosureOut.model_validate(a.closure),
            )
            for a in rows
        ]

    @staticmethod
    def mark_read(db: Session, user: User, alert_id: int) -> None:
        a = db.get(ClosureAlert, alert_id)
        if a is None or a.user_id != user.id:
            raise HTTPException(404, "Alert not found")
        a.read_status = True
        db.commit()
