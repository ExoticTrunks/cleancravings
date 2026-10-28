"""Entity classes. Names and relationships follow the team's Entity Class Diagram
and Data Dictionary (lab2). Where we had to add or simplify something for the
prototype, there's a comment saying so."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Enumerations (match the class diagram) ----------


class StallType(str, enum.Enum):
    COOKED_FOOD = "COOKED_FOOD"
    MARKET_PRODUCE = "MARKET_PRODUCE"
    PIECE_AND_SUNDRIES = "PIECE_AND_SUNDRIES"


class SafeGradeValue(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    NEW = "NEW"


class ClosureReasonType(str, enum.Enum):
    SPRING_CLEANING = "SPRING_CLEANING"
    REPAIRS_AND_REDECORATION = "REPAIRS_AND_REDECORATION"
    OTHER_WORKS = "OTHER_WORKS"


class Verdict(str, enum.Enum):
    SUITABLE = "SUITABLE"
    MODERATE = "MODERATE"
    AVOID = "AVOID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FavouriteTarget(str, enum.Enum):
    CENTRE = "CENTRE"
    STALL = "STALL"
    DISH = "DISH"  # UC-7.0 lets users bookmark dish types too


# ---------- 1. Places & operators ----------


class HawkerCentre(Base):
    __tablename__ = "hawker_centre"

    id: Mapped[int] = mapped_column(primary_key=True)  # NEA dataset _id
    centre_name: Mapped[str] = mapped_column(String(200))
    street_address: Mapped[str | None] = mapped_column(String(300))
    postal_code: Mapped[str | None] = mapped_column(String(6), index=True)
    region: Mapped[str] = mapped_column(String(20), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    number_of_stalls: Mapped[int] = mapped_column(Integer, default=0)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    nea_status: Mapped[str] = mapped_column(String(50), default="Existing")

    stalls: Mapped[list[Stall]] = relationship(back_populates="centre", cascade="all, delete-orphan")
    closures: Mapped[list[ClosurePeriod]] = relationship(
        back_populates="centre", cascade="all, delete-orphan", order_by="ClosurePeriod.start_date"
    )


class Licensee(Base):
    __tablename__ = "licensee"

    licence_number: Mapped[str] = mapped_column(String(30), primary_key=True)
    licensee_name: Mapped[str | None] = mapped_column(String(200))
    licence_status: Mapped[str] = mapped_column(String(20), default="active")
    # Date of the latest SFA export this licence appeared in. A grade only counts as
    # "current" if it came from that export (e.g. "Not Under SAFE" in the latest one -> no grade).
    last_seen_snapshot: Mapped[date | None] = mapped_column(Date)

    stalls: Mapped[list[Stall]] = relationship(back_populates="licensee")
    grades: Mapped[list[SAFEGrade]] = relationship(
        back_populates="licensee", order_by="SAFEGrade.snapshot_date.desc()", cascade="all, delete-orphan"
    )


class Stall(Base):
    __tablename__ = "stall"
    __table_args__ = (UniqueConstraint("licence_number", name="uq_stall_licence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("hawker_centre.id", ondelete="CASCADE"), index=True)
    licence_number: Mapped[str] = mapped_column(ForeignKey("licensee.licence_number"))
    stall_name: Mapped[str] = mapped_column(String(200))
    unit_number: Mapped[str | None] = mapped_column(String(20))
    stall_type: Mapped[StallType] = mapped_column(Enum(StallType), default=StallType.COOKED_FOOD)
    # No official open dataset has these yet, so they stay empty until community data (UC-9.0)
    cuisine: Mapped[str | None] = mapped_column(String(50))
    price_range: Mapped[str | None] = mapped_column(String(30))
    contact_number: Mapped[str | None] = mapped_column(String(20))
    # From HPB's Dining_Concept (Halal / Non-Halal) for stalls in the programme. None = unknown, never False
    halal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    centre: Mapped[HawkerCentre] = relationship(back_populates="stalls")
    licensee: Mapped[Licensee] = relationship(back_populates="stalls")
    hdp: Mapped[ParticipatingStall | None] = relationship(back_populates="stall", uselist=False)


# ---------- 2. Food safety & hygiene ----------


class SAFEGrade(Base):
    """One row per licensee per SFA snapshot. The newest row is the current grade;
    older rows are the grade history (FR-2.3). Snapshot history can't be backfilled,
    which is why the ETL should run on a schedule from early on."""

    __tablename__ = "safe_grade"
    __table_args__ = (UniqueConstraint("licence_number", "snapshot_date", name="uq_grade_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    licence_number: Mapped[str] = mapped_column(ForeignKey("licensee.licence_number", ondelete="CASCADE"), index=True)
    grade_value: Mapped[SafeGradeValue] = mapped_column(Enum(SafeGradeValue))
    under_review: Mapped[bool] = mapped_column(Boolean, default=False)
    # SFA's public search only exposes "licence suspended in the past 1 year" as a flag,
    # not individual demerit points, so TrackRecord is summarised from this.
    suspended_past_year: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)

    licensee: Mapped[Licensee] = relationship(back_populates="grades")


# ---------- 3. Closures ----------


class ClosurePeriod(Base):
    __tablename__ = "closure_period"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("hawker_centre.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason_type: Mapped[ClosureReasonType] = mapped_column(Enum(ClosureReasonType))
    remarks: Mapped[str | None] = mapped_column(Text)
    quarter: Mapped[str | None] = mapped_column(String(2))  # CleaningQuarter, Q1..Q4
    year: Mapped[int | None] = mapped_column(Integer)

    centre: Mapped[HawkerCentre] = relationship(back_populates="closures")

    def is_active(self, today: date) -> bool:  # derived "Active Closure"
        return self.start_date <= today <= self.end_date


# ---------- 4. Healthier eating ----------


class ParticipatingStall(Base):
    """A hawker outlet from HPB's Healthier Dining Partners list, placed at a centre by postal
    code. Linked to one of our stalls when its name matches an SFA stall there (match_method
    says how); otherwise kept at centre level. See etl/hpb_partners_sync.py."""

    __tablename__ = "participating_stall"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    outlet_name: Mapped[str] = mapped_column(String(200))
    postal_code: Mapped[str | None] = mapped_column(String(6), index=True)
    unit_number: Mapped[str | None] = mapped_column(String(20))
    participation_category: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("hawker_centre.id", ondelete="SET NULL"), index=True)
    stall_id: Mapped[int | None] = mapped_column(ForeignKey("stall.id", ondelete="SET NULL"), index=True)
    # "exact" | "fuzzy" | "override" when linked to a stall, else None
    match_method: Mapped[str | None] = mapped_column(String(10))

    stall: Mapped[Stall | None] = relationship(back_populates="hdp")


class DishType(Base):
    """A standard hawker dish profile (UC-6.0). Not stall-specific: no official dataset
    links stalls to dishes. Nutrient values are nullable on purpose; a missing value
    makes the rule engine say INSUFFICIENT_DATA instead of guessing."""

    __tablename__ = "dish_type"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dish_name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    serving_g: Mapped[float | None] = mapped_column(Float)
    energy_kcal: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    contains_pork: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_beef: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(300))


class ClassificationRule(Base):
    """Rules as data: nutrient + operator + threshold + verdict + citation.
    One generic evaluator (app/rules/engine.py) runs all of them."""

    __tablename__ = "classification_rule"

    rule_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    condition: Mapped[str] = mapped_column(String(30), index=True)  # GENERAL, HYPERTENSION, DIABETES...
    nutrient: Mapped[str] = mapped_column(String(30))
    operator: Mapped[str] = mapped_column(String(2))
    threshold: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict))
    citation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / reviewed


# ---------- 5. User & personalisation ----------


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Supabase auth uid
    email: Mapped[str | None] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(100))

    profile: Mapped[UserProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base):
    """Holds DietaryRestriction, DietaryPreference, BudgetRange, HygieneThreshold and
    preferred regions. Stored as columns/JSON lists rather than separate tables to keep
    the prototype small; the class diagram's multiplicities still hold."""

    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    # Added from UC-1.0 / UC-6.0 (health conditions drive the rule engine)
    health_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_min: Mapped[float | None] = mapped_column(Float)
    budget_max: Mapped[float | None] = mapped_column(Float)
    hygiene_threshold: Mapped[SafeGradeValue | None] = mapped_column(Enum(SafeGradeValue))
    preferred_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    date_last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Favourite(Base):
    __tablename__ = "favourite"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_favourite"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[FavouriteTarget] = mapped_column(Enum(FavouriteTarget))
    target_id: Mapped[int] = mapped_column(Integer)
    date_saved: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Visit(Base):
    """FR-5.8 Visit, doubling as the UC-4.0 meal log (optional dish type)."""

    __tablename__ = "visit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    stall_id: Mapped[int] = mapped_column(ForeignKey("stall.id", ondelete="CASCADE"))
    dish_type_id: Mapped[int | None] = mapped_column(ForeignKey("dish_type.id", ondelete="SET NULL"))
    visit_date: Mapped[date] = mapped_column(Date)
    rating: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(300))


class ClosureAlert(Base):
    __tablename__ = "closure_alert"
    __table_args__ = (UniqueConstraint("user_id", "closure_id", name="uq_alert"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    closure_id: Mapped[int] = mapped_column(ForeignKey("closure_period.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    sent_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_status: Mapped[bool] = mapped_column(Boolean, default=False)

    closure: Mapped[ClosurePeriod] = relationship()


# ---------- Implementation-only (not in the domain model) ----------


class SyncRun(Base):
    """ETL run log. Gives the "last updated" timestamps (NFR-2) and run history."""

    __tablename__ = "sync_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(10), index=True)  # NEA / SFA / HPB / REF
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="running")  # ok / failed
    rows: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str | None] = mapped_column(Text)
