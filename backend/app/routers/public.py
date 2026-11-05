"""Endpoints that don't need login (FR-0.1)."""

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import optional_user
from ..config import get_settings
from ..controllers.hawker_centre_controller import HawkerCentreController, StallController
from ..controllers.healthier_eating_controller import HDP_NOTE, HealthierEatingController
from ..controllers.presenters import wants_halal
from ..controllers.recommendation_controller import RecommendationController
from ..db import get_db
from ..geo import REGIONS, today_sg
from ..models import ClassificationRule, SafeGradeValue, SyncRun, User, UserProfile
from ..schemas import (
    CentreDetail,
    CentreSummary,
    DishListOut,
    FreshnessOut,
    GeocodeResult,
    HealthCondition,
    DietaryRestriction,
    RecommendationOut,
    RuleOut,
    SearchOut,
    SourceFreshness,
    StallDetail,
)

router = APIRouter(prefix="/api", tags=["public"])

SOURCE_LABELS = {
    "NEA": "Hawker centres & closures (NEA)",
    "SFA": "SAFE grades & track records (SFA)",
    "HPB": "Healthier Dining Programme (HPB)",
    "REF": "Dish profiles & rules (team)",
}


def _origin(lat: float | None, lng: float | None) -> tuple[float, float] | None:
    return (lat, lng) if lat is not None and lng is not None else None


@router.get("/meta/freshness", response_model=FreshnessOut)
def freshness(db: Session = Depends(get_db)):
    """'Last updated' per source (NFR-2) and staleness flag (NFR-9)."""
    s = get_settings()
    out = []
    now = datetime.now(timezone.utc)
    for src, label in SOURCE_LABELS.items():
        run = db.scalars(
            select(SyncRun).where(SyncRun.source == src, SyncRun.status == "ok").order_by(SyncRun.finished_at.desc())
        ).first()
        last = run.finished_at if run else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)  # SQLite drops tz info
        out.append(
            SourceFreshness(
                source=src,
                label=label,
                last_success=last,
                stale=last is None or (src != "REF" and now - last > timedelta(hours=s.stale_after_hours)),
                is_sample=bool(run and run.is_sample),
            )
        )
    return FreshnessOut(sources=out, any_sample=any(x.is_sample for x in out), today=today_sg())


@router.get("/regions", response_model=list[str])
def regions():
    return REGIONS


@router.get("/centres", response_model=list[CentreSummary])
def list_centres(
    q: str | None = None,
    region: str | None = None,
    min_grade: SafeGradeValue | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = Query(None, gt=0),
    db: Session = Depends(get_db),
):
    return HawkerCentreController.list_centres(db, today_sg(), q, region, min_grade, _origin(lat, lng), radius_km)


@router.get("/centres/{centre_id}", response_model=CentreDetail)
def centre_detail(
    centre_id: int,
    min_grade: SafeGradeValue | None = None,
    halal_only: bool | None = Query(None, description="Omit to follow the signed-in user's HALAL restriction"),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    if halal_only is None:
        halal_only = wants_halal(db.get(UserProfile, user.id) if user else None)
    return HawkerCentreController.centre_detail(db, centre_id, today_sg(), min_grade, halal_only)


@router.get(
    "/centres/{centre_id}/photo",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}, "description": "The centre's photo from NEA"}, 404: {}, 502: {}},
)
def centre_photo(centre_id: int, db: Session = Depends(get_db)):
    data, ctype = HawkerCentreController.photo(db, centre_id)
    return Response(data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/stalls/{stall_id}", response_model=StallDetail)
def stall_detail(stall_id: int, db: Session = Depends(get_db)):
    return StallController.stall_detail(db, stall_id, today_sg())


@router.get("/search", response_model=SearchOut)
def search(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    return HawkerCentreController.search(db, q, today_sg())


@router.get("/hdp-note", response_model=str)
def hdp_note():
    return HDP_NOTE


@router.get("/dishes", response_model=DishListOut)
def dishes(
    conditions: list[HealthCondition] = Query([]),
    restrictions: list[DietaryRestriction] = Query([]),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    """UC-6.0. Logged-in users get their saved profile unless the query overrides it."""
    prefer_low_sodium = False
    if user and not conditions and not restrictions and (p := db.get(UserProfile, user.id)):
        conditions, restrictions = p.health_conditions or [], p.dietary_restrictions or []
        prefer_low_sodium = "LOWER_SODIUM" in (p.dietary_preferences or [])
    return HealthierEatingController.assess_dishes(db, list(conditions), list(restrictions), prefer_low_sodium)


@router.get("/rules", response_model=list[RuleOut])
def rules(db: Session = Depends(get_db)):
    return db.scalars(select(ClassificationRule).order_by(ClassificationRule.condition, ClassificationRule.rule_id)).all()


@router.get("/recommendations", response_model=RecommendationOut)
def recommendations(
    lat: float | None = None,
    lng: float | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    return RecommendationController.recommend(db, today_sg(), user, _origin(lat, lng), limit)


@router.get("/geocode", response_model=list[GeocodeResult])
def geocode(q: str = Query(..., min_length=2)):
    """UC-2.0 AC.1: manual location. Proxied so the client only ever talks to our API (NFR-5)."""
    try:
        r = httpx.get(
            "https://www.onemap.gov.sg/api/common/elastic/search",
            params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
            timeout=8,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, "Location search is unavailable right now") from e
    out = []
    for hit in r.json().get("results", [])[:8]:
        try:
            out.append(
                GeocodeResult(
                    label=hit.get("SEARCHVAL") or hit.get("ADDRESS") or q,
                    latitude=float(hit["LATITUDE"]),
                    longitude=float(hit["LONGITUDE"]),
                    postal_code=hit.get("POSTAL") if hit.get("POSTAL") not in (None, "NIL") else None,
                )
            )
        except (KeyError, ValueError):
            continue
    return out
