"""API contract. The frontend's TypeScript types are generated from these via
FastAPI's OpenAPI schema (frontend: npm run gen:api), so renaming a field here breaks
the frontend build instead of showing 'undefined' on demo day."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ClosureReasonType, FavouriteTarget, SafeGradeValue, StallType, Verdict

CentreState = Literal["open", "closing_soon", "closed", "not_operating"]
HealthCondition = Literal["HYPERTENSION", "DIABETES", "HIGH_CHOLESTEROL"]
# HALAL filters stalls (confirmed halal only), not dishes: no dish data says whether it's halal
DietaryRestriction = Literal["NO_PORK", "NO_BEEF", "VEGETARIAN", "HALAL"]
HdpMatchMethod = Literal["exact", "fuzzy", "override"]
DietaryPreference = Literal["HEALTHIER_CHOICE", "LOWER_SODIUM"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- meta ----------


class SourceFreshness(BaseModel):
    source: Literal["NEA", "SFA", "HPB", "REF"]
    label: str
    last_success: datetime | None
    stale: bool
    is_sample: bool


class FreshnessOut(BaseModel):
    sources: list[SourceFreshness]
    any_sample: bool
    today: date


# ---------- closures / centres ----------


class ClosureOut(ORM):
    id: int
    start_date: date
    end_date: date
    reason_type: ClosureReasonType
    remarks: str | None
    quarter: str | None


class CentreStatus(BaseModel):
    state: CentreState
    active_closure: ClosureOut | None = None
    next_closure: ClosureOut | None = None
    days_to_next: int | None = None
    reopens_on: date | None = None


class GradeSummary(BaseModel):
    A: int = 0
    B: int = 0
    C: int = 0
    NEW: int = 0
    ungraded: int = 0


class CentreSummary(BaseModel):
    id: int
    centre_name: str
    street_address: str | None
    postal_code: str | None
    region: str
    latitude: float
    longitude: float
    number_of_stalls: int
    photo_url: str | None
    status: CentreStatus
    distance_km: float | None = None
    hdp_count: int = 0
    grades: GradeSummary


class SafeGradeOut(ORM):
    grade_value: SafeGradeValue
    under_review: bool
    snapshot_date: date


class StallSummary(BaseModel):
    id: int
    centre_id: int
    stall_name: str
    unit_number: str | None
    cuisine: str | None
    price_range: str | None
    safe_grade: SafeGradeOut | None
    suspended_past_year: bool
    hdp_participant: bool
    hdp_category: str | None
    hdp_match_method: HdpMatchMethod | None = Field(None, description="How the HPB listing was matched to this stall")
    halal: bool | None = Field(None, description="From the HPB listing. null = unknown, not non-halal")


class CentreDetail(CentreSummary):
    closures: list[ClosureOut]
    stalls: list[StallSummary]
    stalls_hidden_by_threshold: int = 0
    halal_only: bool = False
    stalls_hidden_by_halal: int = Field(0, description="Hidden because halal status is unknown or non-halal")
    hdp_outlets_without_stall_match: list[str] = []


class TrackRecordOut(BaseModel):
    observation_window: str = "Past 12 months"
    suspended_past_year: bool
    total_demerit_points: int | None = Field(None, description="SFA does not publish points per licensee, so this is null for now")
    grade_history: list[SafeGradeOut]
    last_updated: date | None


class StallDetail(StallSummary):
    stall_type: StallType
    contact_number: str | None
    licence_number: str
    licensee_name: str | None
    centre: CentreSummary
    track_record: TrackRecordOut
    operating_hours_available: bool = False


# ---------- dishes / rules ----------


class FindingOut(BaseModel):
    rule_id: str
    condition: str
    nutrient: str
    message: str
    verdict: Verdict | None
    citation: str


class Nutrients(BaseModel):
    energy_kcal: float | None
    sodium_mg: float | None
    sugar_g: float | None
    saturated_fat_g: float | None
    protein_g: float | None


class DishAssessment(BaseModel):
    id: int
    dish_name: str
    category: str
    serving_g: float | None
    nutrients: Nutrients
    verdict: Verdict
    findings: list[FindingOut]
    unchecked_conditions: list[str]
    contains_pork: bool
    contains_beef: bool
    is_vegetarian: bool
    source: str


class DishListOut(BaseModel):
    conditions: list[str]
    restrictions: list[str]
    dishes: list[DishAssessment]
    excluded_by_restriction: int
    disclaimer: str


class RuleOut(ORM):
    rule_id: str
    condition: str
    nutrient: str
    operator: str
    threshold: float
    unit: str
    verdict: Verdict
    status: str
    citation: str


# ---------- user ----------


class MeOut(BaseModel):
    id: str
    email: str | None
    display_name: str | None
    has_profile: bool


class ProfileIn(BaseModel):
    health_conditions: list[HealthCondition] = []
    dietary_restrictions: list[DietaryRestriction] = []
    dietary_preferences: list[DietaryPreference] = []
    budget_min: float | None = Field(None, ge=0)
    budget_max: float | None = Field(None, ge=0)
    hygiene_threshold: SafeGradeValue | None = None
    preferred_regions: list[str] = []


class ProfileOut(ProfileIn):
    date_last_updated: datetime | None = None


class RecommendationItem(BaseModel):
    stall: StallSummary
    centre_name: str
    centre_region: str
    distance_km: float | None
    reasons: list[str]


class RecommendationOut(BaseModel):
    generated_at: datetime
    used_profile: bool
    location_used: bool
    items: list[RecommendationItem]
    total_candidates: int
    excluded_closed: int
    excluded_by_hygiene: int
    halal_only: bool = False
    halal_confirmed: int = Field(0, description="Candidates with confirmed halal status when halal_only is on")
    excluded_by_halal: int = 0
    disclaimer: str


class FavouriteIn(BaseModel):
    target_type: FavouriteTarget
    target_id: int


class FavouriteOut(BaseModel):
    id: int
    target_type: FavouriteTarget
    target_id: int
    date_saved: datetime
    label: str
    subtitle: str | None
    unavailable: bool = False
    centre_status: CentreStatus | None = None


class VisitIn(BaseModel):
    stall_id: int
    dish_type_id: int | None = None
    visit_date: date | None = None
    rating: int | None = Field(None, ge=1, le=5)
    note: str | None = Field(None, max_length=300)


class VisitOut(BaseModel):
    id: int
    stall_id: int
    stall_name: str
    centre_name: str
    dish_name: str | None
    visit_date: date
    rating: int | None
    note: str | None


class AlertOut(BaseModel):
    id: int
    message: str
    sent_timestamp: datetime
    read_status: bool
    centre_id: int
    closure: ClosureOut


# ---------- search / geocode ----------


class StallHit(StallSummary):
    centre_name: str


class SearchOut(BaseModel):
    query: str
    centres: list[CentreSummary]
    stalls: list[StallHit]
    dishes: list[str]


class GeocodeResult(BaseModel):
    label: str
    latitude: float
    longitude: float
    postal_code: str | None
