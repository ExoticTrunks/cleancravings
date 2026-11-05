"""RecommendationController (FR-5.6, FR-3.3, FR-5.9 stretch, NFR-6).

The score is internal only. Per the data dictionary it's never shown as a number;
the client gets the ordered list plus plain-language reasons (contributing factors)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..geo import haversine_km
from ..models import Favourite, FavouriteTarget, HawkerCentre, Licensee, SafeGradeValue, Stall, StallType, User, UserProfile, Visit
from ..schemas import CentreStatus, RecommendationItem, RecommendationOut, StallSummary
from .cache import cached
from .closure_controller import ClosureController
from .hygiene_controller import GRADE_RANK
from .presenters import stall_summary, wants_halal

DISCLAIMER = (
    "Suggestions are ordered using official SFA, NEA and HPB data plus your preferences. "
    "They aren't a guarantee of food safety or that a dish suits your health needs."
)
GRADE_POINTS = {SafeGradeValue.A: 1.0, SafeGradeValue.B: 0.7, SafeGradeValue.NEW: 0.5, SafeGradeValue.C: 0.1}
MAX_KM = 8.0
PER_CENTRE_CAP = 3  # keep the list varied instead of 20 stalls from one centre


@dataclass(frozen=True)
class _CandidateCentre:
    id: int
    centre_name: str
    region: str
    latitude: float
    longitude: float
    status: CentreStatus
    stalls: list[StallSummary]  # Cooked Food only (FR-1.6)


def _candidate_centres(db: Session, today: date) -> list[_CandidateCentre]:
    """Every centre with its status and stall summaries. The same for every user, so it's
    cached (controllers/cache.py); only the user's own profile, bookmarks and ratings are
    read per request (NFR-1)."""

    def build() -> list[_CandidateCentre]:
        centres = db.scalars(
            select(HawkerCentre).options(
                selectinload(HawkerCentre.closures),
                selectinload(HawkerCentre.stalls).selectinload(Stall.licensee).selectinload(Licensee.grades),
                selectinload(HawkerCentre.stalls).selectinload(Stall.hdp),
            )
        ).all()
        return [
            _CandidateCentre(
                id=c.id,
                centre_name=c.centre_name,
                region=c.region,
                latitude=c.latitude,
                longitude=c.longitude,
                status=ClosureController.centre_status(c, today),
                stalls=[stall_summary(s) for s in c.stalls if s.stall_type == StallType.COOKED_FOOD],
            )
            for c in centres
        ]

    return cached("recommendation_centres", db, today, build)


class RecommendationController:
    @staticmethod
    def recommend(
        db: Session,
        today: date,
        user: User | None = None,
        origin: tuple[float, float] | None = None,
        limit: int = 20,
    ) -> RecommendationOut:
        profile = db.get(UserProfile, user.id) if user else None
        threshold = profile.hygiene_threshold if profile else None
        regions = set(profile.preferred_regions or []) if profile else set()
        wants_healthier = bool(profile and "HEALTHIER_CHOICE" in (profile.dietary_preferences or []))
        halal_only = wants_halal(profile)

        fav_centres: set[int] = set()
        fav_stalls: set[int] = set()
        ratings: dict[int, int] = {}
        if user:
            for f in db.scalars(select(Favourite).where(Favourite.user_id == user.id)):
                (fav_centres if f.target_type == FavouriteTarget.CENTRE else fav_stalls).add(f.target_id)
            for v in db.scalars(select(Visit).where(Visit.user_id == user.id, Visit.rating.is_not(None)).order_by(Visit.visit_date)):
                ratings[v.stall_id] = v.rating  # latest rating wins

        scored: list[tuple[float, RecommendationItem]] = []
        excluded_closed = excluded_hygiene = excluded_halal = halal_confirmed = total = 0
        for c in _candidate_centres(db, today):
            status = c.status
            total += len(c.stalls)
            if status.state in ("closed", "not_operating"):
                excluded_closed += len(c.stalls)  # FR-3.3
                continue
            dist = haversine_km(origin[0], origin[1], c.latitude, c.longitude) if origin else None
            if dist is not None and dist > MAX_KM:
                continue
            for s in c.stalls:
                grade = s.safe_grade.grade_value if s.safe_grade else None
                # Same rule as HygieneController.passes_threshold: no current grade fails any minimum
                if threshold and (grade is None or GRADE_RANK[grade] < GRADE_RANK[threshold]):
                    excluded_hygiene += 1
                    continue
                if halal_only:
                    if s.halal is not True:  # as presenters.confirmed_halal: None means unknown
                        excluded_halal += 1
                        continue
                    halal_confirmed += 1
                score, reasons = 0.0, []
                if dist is not None:
                    score += 3 * max(0.0, 1 - dist / MAX_KM)
                    reasons.append(f"{dist:.1f} km away")
                score += 2 * (GRADE_POINTS[grade] if grade else 0.3)
                if grade == SafeGradeValue.A:
                    reasons.append("SAFE Grade A")
                if s.hdp_participant:
                    score += 2 if wants_healthier else 0.5
                    reasons.append("Healthier Dining Programme stall")
                if c.region in regions:
                    score += 1.5
                    reasons.append(f"In your preferred region ({c.region})")
                if s.id in fav_stalls or c.id in fav_centres:
                    score += 1
                    reasons.append("In your bookmarks")
                if (r := ratings.get(s.id)) is not None:
                    score += 1 if r >= 4 else -1 if r <= 2 else 0
                    if r >= 4:
                        reasons.append(f"You rated it {r}/5")
                if status.state == "closing_soon":
                    reasons.append(f"Heads up: centre closes in {status.days_to_next} day(s)")
                scored.append(
                    (
                        score,
                        RecommendationItem(
                            stall=s,
                            centre_name=c.centre_name,
                            centre_region=c.region,
                            distance_km=round(dist, 2) if dist is not None else None,
                            reasons=reasons,
                        ),
                    )
                )

        scored.sort(key=lambda t: (-t[0], t[1].stall.stall_name))
        per_centre: dict[int, int] = defaultdict(int)
        items: list[RecommendationItem] = []
        for _, item in scored:
            if per_centre[item.stall.centre_id] >= PER_CENTRE_CAP:
                continue
            per_centre[item.stall.centre_id] += 1
            items.append(item)
            if len(items) >= limit:
                break

        return RecommendationOut(
            generated_at=datetime.now(timezone.utc),
            used_profile=profile is not None,
            location_used=origin is not None,
            items=items,
            total_candidates=total,
            excluded_closed=excluded_closed,
            excluded_by_hygiene=excluded_hygiene,
            halal_only=halal_only,
            halal_confirmed=halal_confirmed,
            excluded_by_halal=excluded_halal,
            disclaimer=DISCLAIMER,
        )
