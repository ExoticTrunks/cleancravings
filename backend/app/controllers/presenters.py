"""Turn entities into API shapes. Shared by several controllers."""

from datetime import date

from ..geo import haversine_km
from ..models import HawkerCentre, Stall, UserProfile
from ..schemas import CentreSummary, SafeGradeOut, StallSummary
from .closure_controller import ClosureController
from .hygiene_controller import HygieneController


def stall_summary(stall: Stall) -> StallSummary:
    g = HygieneController.current_grade(stall.licensee)
    return StallSummary(
        id=stall.id,
        centre_id=stall.centre_id,
        stall_name=stall.stall_name,
        unit_number=stall.unit_number,
        cuisine=stall.cuisine,
        price_range=stall.price_range,
        safe_grade=SafeGradeOut.model_validate(g) if g else None,
        suspended_past_year=HygieneController.suspended_past_year(stall.licensee),
        hdp_participant=stall.hdp is not None,
        hdp_category=stall.hdp.participation_category if stall.hdp else None,
        hdp_match_method=stall.hdp.match_method if stall.hdp else None,
        halal=stall.halal,
    )


def wants_halal(profile: UserProfile | None) -> bool:
    return bool(profile and "HALAL" in (profile.dietary_restrictions or []))


def confirmed_halal(stall: Stall | StallSummary) -> bool:
    # Only an explicit True counts. None means the stall hasn't published it, not that it's non-halal
    return stall.halal is True


def centre_summary(
    centre: HawkerCentre, today: date, origin: tuple[float, float] | None = None, hdp_count: int = 0
) -> CentreSummary:
    dist = round(haversine_km(origin[0], origin[1], centre.latitude, centre.longitude), 2) if origin else None
    return CentreSummary(
        id=centre.id,
        centre_name=centre.centre_name,
        street_address=centre.street_address,
        postal_code=centre.postal_code,
        region=centre.region,
        latitude=centre.latitude,
        longitude=centre.longitude,
        number_of_stalls=centre.number_of_stalls,
        photo_url=centre.photo_url,
        status=ClosureController.centre_status(centre, today),
        distance_km=dist,
        hdp_count=hdp_count,
        grades=HygieneController.summary(centre.stalls),
    )
