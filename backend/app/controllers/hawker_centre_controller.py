"""HawkerCentreController (FR-1.1 to FR-1.4, FR-2.5) and StallController (FR-1.5 to FR-1.7)."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..geo import haversine_km
from ..models import DishType, HawkerCentre, Licensee, ParticipatingStall, SafeGradeValue, Stall, StallType
from ..schemas import CentreDetail, CentreSummary, ClosureOut, SearchOut, StallDetail, StallHit
from .cache import cached
from .hygiene_controller import GRADE_RANK, HygieneController
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
    def _cached_summaries(cls, db: Session, today: date) -> list[tuple[CentreSummary, int, str]]:
        """Centre summaries without distance, plus the best current grade rank among each
        centre's Cooked Food stalls and the text that search matches against. Cached (see
        controllers/cache.py), so each request only works out distance (NFR-1)."""

        def build() -> list[tuple[CentreSummary, int, str]]:
            counts = cls.hdp_counts(db)
            rows = []
            for c in db.scalars(_centre_query()).all():
                grades = (HygieneController.current_grade(s.licensee) for s in _cooked(c.stalls))
                best_rank = max((GRADE_RANK[g.grade_value] for g in grades if g is not None), default=0)
                haystack = f"{c.centre_name} {c.street_address or ''} {c.postal_code or ''}".lower()
                rows.append((centre_summary(c, today, None, counts.get(c.id, 0)), best_rank, haystack))
            return rows

        return cached("centre_summaries", db, today, build)

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
        out: list[CentreSummary] = []
        needle = (q or "").strip().lower()
        for base, best_rank, haystack in cls._cached_summaries(db, today):
            if region and base.region != region:
                continue
            if needle and needle not in haystack:
                continue
            # Same result as passes_threshold() on each Cooked Food stall (FR-2.5)
            if min_grade and best_rank < GRADE_RANK[min_grade]:
                continue
            dist = round(haversine_km(origin[0], origin[1], base.latitude, base.longitude), 2) if origin else None
            if radius_km and dist is not None and dist > radius_km:
                continue
            out.append(base.model_copy(update={"distance_km": dist}))
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
