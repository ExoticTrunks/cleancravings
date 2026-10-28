"""HawkerCentreController (FR-1.1 to FR-1.4, FR-2.5) and StallController (FR-1.5 to FR-1.7)."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import DishType, HawkerCentre, Licensee, ParticipatingStall, SafeGradeValue, Stall, StallType
from ..schemas import CentreDetail, CentreSummary, ClosureOut, SearchOut, StallDetail, StallHit
from .hygiene_controller import HygieneController
from .presenters import centre_summary, confirmed_halal, stall_summary


def _centre_query():
    return select(HawkerCentre).options(
        selectinload(HawkerCentre.closures),
        selectinload(HawkerCentre.stalls).selectinload(Stall.licensee).selectinload(Licensee.grades),
        selectinload(HawkerCentre.stalls).selectinload(Stall.hdp),
    )


def _cooked(stalls: list[Stall]) -> list[Stall]:
    # FR-1.6: only Cooked Food stalls are ever surfaced
    return [s for s in stalls if s.stall_type == StallType.COOKED_FOOD]


class HawkerCentreController:
    @staticmethod
    def hdp_counts(db: Session) -> dict[int, int]:
        rows = db.execute(
            select(ParticipatingStall.centre_id, func.count())
            .where(ParticipatingStall.centre_id.is_not(None))
            .group_by(ParticipatingStall.centre_id)
        )
        return {cid: n for cid, n in rows}

    @classmethod
    def list_centres(
        cls,
        db: Session,
        today: date,
        q: str | None = None,
        region: str | None = None,
        min_grade: SafeGradeValue | None = None,
        origin: tuple[float, float] | None = None,
        radius_km: float | None = None,
    ) -> list[CentreSummary]:
        centres = db.scalars(_centre_query()).all()
        counts = cls.hdp_counts(db)
        out: list[CentreSummary] = []
        needle = (q or "").strip().lower()
        for c in centres:
            if region and c.region != region:
                continue
            if needle and needle not in f"{c.centre_name} {c.street_address or ''} {c.postal_code or ''}".lower():
                continue
            if min_grade and not any(HygieneController.passes_threshold(s, min_grade) for s in _cooked(c.stalls)):
                continue
            summary = centre_summary(c, today, origin, counts.get(c.id, 0))
            if radius_km and summary.distance_km is not None and summary.distance_km > radius_km:
                continue
            out.append(summary)
        # Name matches before address matches, then nearest first
        out.sort(
            key=lambda s: (
                bool(needle) and needle not in s.centre_name.lower(),
                s.distance_km if s.distance_km is not None else 0,
                s.centre_name,
            )
        )
        return out

    @classmethod
    def centre_detail(
        cls, db: Session, centre_id: int, today: date, min_grade: SafeGradeValue | None = None, halal_only: bool = False
    ) -> CentreDetail:
        c = db.scalars(_centre_query().where(HawkerCentre.id == centre_id)).first()
        if c is None:
            raise HTTPException(404, "Hawker centre not found")
        cooked = _cooked(c.stalls)
        graded = [s for s in cooked if HygieneController.passes_threshold(s, min_grade)]
        shown = [s for s in graded if confirmed_halal(s)] if halal_only else graded
        unmatched = db.scalars(
            select(ParticipatingStall.outlet_name).where(
                ParticipatingStall.centre_id == c.id, ParticipatingStall.stall_id.is_(None)
            )
        ).all()
        base = centre_summary(c, today, None, cls.hdp_counts(db).get(c.id, 0))
        return CentreDetail(
            **base.model_dump(),
            closures=[ClosureOut.model_validate(x) for x in c.closures if x.end_date >= today],
            stalls=sorted((stall_summary(s) for s in shown), key=lambda s: s.unit_number or "zzz"),
            stalls_hidden_by_threshold=len(cooked) - len(graded),
            halal_only=halal_only,
            stalls_hidden_by_halal=len(graded) - len(shown),
            hdp_outlets_without_stall_match=list(unmatched),
        )

    @classmethod
    def search(cls, db: Session, q: str, today: date) -> SearchOut:
        needle = f"%{q.strip()}%"
        centres = cls.list_centres(db, today, q=q)
        stalls = db.scalars(
            select(Stall)
            .options(selectinload(Stall.licensee).selectinload(Licensee.grades), selectinload(Stall.hdp), selectinload(Stall.centre))
            .where(Stall.stall_type == StallType.COOKED_FOOD, or_(Stall.stall_name.ilike(needle), Stall.cuisine.ilike(needle)))
            .limit(30)
        ).all()
        dishes = db.scalars(select(DishType.dish_name).where(DishType.dish_name.ilike(needle)).limit(10)).all()
        return SearchOut(
            query=q,
            centres=centres[:20],
            stalls=[StallHit(**stall_summary(s).model_dump(), centre_name=s.centre.centre_name) for s in stalls],
            dishes=list(dishes),
        )


class StallController:
    @staticmethod
    def stall_detail(db: Session, stall_id: int, today: date) -> StallDetail:
        s = db.scalars(
            select(Stall)
            .options(selectinload(Stall.licensee).selectinload(Licensee.grades), selectinload(Stall.hdp))
            .where(Stall.id == stall_id, Stall.stall_type == StallType.COOKED_FOOD)
        ).first()
        if s is None:
            raise HTTPException(404, "Stall not found")
        centre = db.scalars(_centre_query().where(HawkerCentre.id == s.centre_id)).one()
        return StallDetail(
            **stall_summary(s).model_dump(),
            stall_type=s.stall_type,
            contact_number=s.contact_number,
            licence_number=s.licence_number,
            licensee_name=s.licensee.licensee_name if s.licensee else None,
            centre=centre_summary(centre, today, None, HawkerCentreController.hdp_counts(db).get(centre.id, 0)),
            track_record=HygieneController.track_record(s),
        )
