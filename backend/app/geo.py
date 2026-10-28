"""Distance and region helpers. Plain haversine instead of PostGIS: with ~123 centres
and a few thousand stalls this runs in well under a millisecond (team decision,
see the AI tech stack evaluation, section 5)."""

import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

SG_TZ = ZoneInfo("Asia/Singapore")

REGIONS = ["Central", "East", "North", "North-East", "West"]

# Rough centre points of the five URA planning regions. Nearest-centroid is good enough
# for browse/filter; swap for point-in-polygon on URA's region boundary layer later.
_REGION_CENTROIDS = {
    "Central": (1.3000, 103.8350),
    "East": (1.3450, 103.9450),
    "North": (1.4300, 103.8000),
    "North-East": (1.3750, 103.8900),
    "West": (1.3500, 103.7200),
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def region_for(lat: float, lng: float) -> str:
    return min(_REGION_CENTROIDS, key=lambda k: haversine_km(lat, lng, *_REGION_CENTROIDS[k]))


def postal_codes(address: str | None) -> list[str]:
    """All postal codes in an address. NEA lists centres spanning two blocks as
    'Singapore 430013/430014', and SFA stalls can use either one."""
    if not address:
        return []
    m = re.search(r"singapore\s*\(?(\d{6}(?:\s*/\s*\d{6})*)\)?", address, re.I)
    return re.findall(r"\d{6}", m.group(1)) if m else re.findall(r"\b\d{6}\b", address)[:1]


def postal_code(address: str | None) -> str | None:
    codes = postal_codes(address)
    return codes[0] if codes else None


def unit_number(address: str | None) -> str | None:
    if not address:
        return None
    m = re.search(r"#\s*([0-9A-Z]{1,3}\s*-\s*[0-9A-Z]{1,5})", address, re.I)
    if m:
        return m.group(1).replace(" ", "").upper()
    # Some centres (Maxwell, Amoy Street...) use plain 3-digit stall numbers in SFA's
    # export: "1 KADAYANALLUR STREET 056,Singapore 069184"
    m = re.search(r"[A-Z]\s+(\d{3})\s*,", address, re.I)
    return m.group(1) if m else None


def today_sg(now: datetime | None = None) -> date:
    return (now or datetime.now(SG_TZ)).astimezone(SG_TZ).date()
