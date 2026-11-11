import httpx
import pytest

from tests.conftest import AUTH


def test_freshness_flags_sample(client):
    j = client.get("/api/meta/freshness").json()
    assert j["any_sample"] is True
    assert {s["source"] for s in j["sources"]} == {"NEA", "SFA", "HPB", "REF"}


def test_centres_list_and_filters(client):
    all_ = client.get("/api/centres").json()
    assert len(all_) == 15
    west = client.get("/api/centres", params={"region": "West"}).json()
    assert west and all(c["region"] == "West" for c in west)
    near = client.get("/api/centres", params={"lat": 1.3483, "lng": 103.6831, "radius_km": 5}).json()
    assert near and all(c["distance_km"] <= 5 for c in near)
    assert near == sorted(near, key=lambda c: c["distance_km"])


def test_closed_centre_status(client):
    amoy = next(c for c in client.get("/api/centres").json() if c["centre_name"].startswith("Amoy"))
    assert amoy["status"]["state"] == "closed"
    assert amoy["status"]["active_closure"]["reason_type"] == "REPAIRS_AND_REDECORATION"


def test_centre_detail_threshold(client):
    full = client.get("/api/centres/1").json()
    only_a = client.get("/api/centres/1", params={"min_grade": "A"}).json()
    assert all(s["safe_grade"]["grade_value"] == "A" for s in only_a["stalls"])
    assert only_a["stalls_hidden_by_threshold"] == len(full["stalls"]) - len(only_a["stalls"])


def test_stall_detail_has_track_record(client):
    sid = client.get("/api/centres/1").json()["stalls"][0]["id"]
    s = client.get(f"/api/stalls/{sid}").json()
    assert s["track_record"]["total_demerit_points"] is None  # not published by SFA
    assert s["track_record"]["grade_history"]
    assert s["stall_type"] == "COOKED_FOOD"


def test_recommendations_exclude_closed_centres(client):
    centres = client.get("/api/centres").json()
    closed = {c["id"] for c in centres if c["status"]["state"] == "closed"}
    r = client.get("/api/recommendations").json()
    assert closed and r["excluded_closed"] > 0
    assert not any(i["stall"]["centre_id"] in closed for i in r["items"])
    assert "guarantee" in r["disclaimer"]
    assert all("score" not in i for i in r["items"])  # NFR-6: no bare number


def test_login_required(client):
    assert client.get("/api/me/profile").status_code == 401
    assert client.post("/api/me/favourites", json={"target_type": "CENTRE", "target_id": 1}).status_code == 401


def test_profile_drives_recommendations(client):
    assert client.put("/api/me/profile", json={"hygiene_threshold": "A"}, headers=AUTH).status_code == 200
    r = client.get("/api/recommendations", headers=AUTH).json()
    assert r["used_profile"] and r["excluded_by_hygiene"] > 0
    assert all(i["stall"]["safe_grade"]["grade_value"] == "A" for i in r["items"])


def test_profile_validation(client):
    bad = client.put("/api/me/profile", json={"budget_min": 10, "budget_max": 5}, headers=AUTH)
    assert bad.status_code == 422
    assert client.put("/api/me/profile", json={"preferred_regions": ["Mars"]}, headers=AUTH).status_code == 422


def test_favourite_creates_closure_alert(client):
    soon = next(c for c in client.get("/api/centres").json() if c["status"]["state"] in ("closing_soon", "closed"))
    f = client.post("/api/me/favourites", json={"target_type": "CENTRE", "target_id": soon["id"]}, headers=AUTH)
    assert f.status_code == 201
    alerts = client.get("/api/me/alerts", headers=AUTH).json()
    assert any(a["centre_id"] == soon["id"] for a in alerts)
    # idempotent: asking again doesn't duplicate
    assert len(client.get("/api/me/alerts", headers=AUTH).json()) == len(alerts)


def test_saved_centres_carry_full_status(client):
    """The Saved page's status pill needs the day count and reopening date, not only the state (FR-5.7)."""
    other = {"Authorization": "Bearer dev:saved-status@example.com"}
    centres = client.get("/api/centres").json()
    for state, field in (("closing_soon", "days_to_next"), ("closed", "reopens_on")):
        c = next(x for x in centres if x["status"]["state"] == state)
        assert client.post("/api/me/favourites", json={"target_type": "CENTRE", "target_id": c["id"]}, headers=other).status_code == 201
        saved = next(f for f in client.get("/api/me/favourites", headers=other).json() if f["target_id"] == c["id"])
        assert saved["centre_status"]["state"] == state
        assert saved["centre_status"][field] is not None
        assert saved["centre_status"][field] == c["status"][field]


def test_visit_log(client):
    sid = client.get("/api/centres/2").json()["stalls"][0]["id"]
    v = client.post("/api/me/visits", json={"stall_id": sid, "rating": 5, "note": "shiok"}, headers=AUTH)
    assert v.status_code == 201
    assert client.post("/api/me/visits", json={"stall_id": sid, "rating": 9}, headers=AUTH).status_code == 422
    assert client.get("/api/me/visits", headers=AUTH).json()[0]["rating"] == 5


def test_dishes_respect_restrictions(client):
    j = client.get("/api/dishes", params={"restrictions": ["NO_PORK"]}).json()
    assert j["excluded_by_restriction"] > 0
    assert not any(d["contains_pork"] for d in j["dishes"])
    verdicts = [d["verdict"] for d in j["dishes"]]
    order = {"SUITABLE": 0, "MODERATE": 1, "INSUFFICIENT_DATA": 2, "AVOID": 3}
    assert verdicts == sorted(verdicts, key=order.get)


HALAL_USER = {"Authorization": "Bearer dev:halal-tester@example.com"}


def test_stall_halal_unknown_is_null_not_false(client):
    stalls = client.get("/api/centres/1").json()["stalls"]
    by_status = {v: [s for s in stalls if s["halal"] is v] for v in (True, False, None)}
    assert all(by_status.values()), "sample centre 1 should have halal, non-halal and unknown stalls"
    unknown = client.get(f"/api/stalls/{by_status[None][0]['id']}").json()
    assert unknown["halal"] is None and unknown["hdp_match_method"] is None
    listed = client.get(f"/api/stalls/{by_status[True][0]['id']}").json()
    assert listed["halal"] is True and listed["hdp_participant"] and listed["hdp_match_method"] == "exact"


def test_centre_halal_filter_keeps_only_confirmed(client):
    full = client.get("/api/centres/1").json()
    assert full["halal_only"] is False and full["stalls_hidden_by_halal"] == 0
    j = client.get("/api/centres/1", params={"halal_only": True}).json()
    assert j["halal_only"] is True and j["stalls"]
    assert all(s["halal"] is True for s in j["stalls"])  # unknown and non-halal both hidden
    assert j["stalls_hidden_by_halal"] == len(full["stalls"]) - len(j["stalls"])
    # The hygiene filter still applies first, and is counted separately
    both = client.get("/api/centres/1", params={"halal_only": True, "min_grade": "A"}).json()
    assert both["stalls_hidden_by_threshold"] == client.get("/api/centres/1", params={"min_grade": "A"}).json()["stalls_hidden_by_threshold"]


def test_halal_restriction_in_profile(client):
    assert client.put("/api/me/profile", json={"dietary_restrictions": ["HALAL"]}, headers=HALAL_USER).status_code == 200
    r = client.get("/api/recommendations", headers=HALAL_USER).json()
    assert r["halal_only"] is True and r["items"]
    assert all(i["stall"]["halal"] is True for i in r["items"])
    assert r["excluded_by_halal"] > 0 and r["halal_confirmed"] >= len(r["items"])
    # Centre page follows the profile unless the request says otherwise
    centre = client.get("/api/centres/1", headers=HALAL_USER).json()
    assert centre["halal_only"] is True and all(s["halal"] is True for s in centre["stalls"])
    off = client.get("/api/centres/1", params={"halal_only": False}, headers=HALAL_USER).json()
    assert off["halal_only"] is False and any(s["halal"] is None for s in off["stalls"])
    # Without the restriction nothing is filtered, and unknown stalls are still recommended
    anon = client.get("/api/recommendations").json()
    assert anon["halal_only"] is False and anon["excluded_by_halal"] == 0
    assert any(i["stall"]["halal"] is None for i in anon["items"])


def test_search(client):
    j = client.get("/api/search", params={"q": "maxwell"}).json()
    assert j["centres"][0]["centre_name"] == "Maxwell Food Centre"


def test_centre_photo_missing_is_404(client):
    # The sample NEA rows have no photourl
    assert client.get("/api/centres/1/photo").status_code == 404


def test_centre_photo_is_proxied_from_nea_and_cached(client, monkeypatch):
    from app.controllers import hawker_centre_controller as hcc

    calls = []

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg"}
        content = b"\xff\xd8fake-jpeg"
        url = httpx.URL("https://www.nea.gov.sg/images/x.jpg")

    def fake_get(url, **kw):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(hcc, "_photo_source", lambda db, cid: "http://www.nea.gov.sg/images/x.jpg")
    monkeypatch.setattr(hcc.httpx, "get", fake_get)
    monkeypatch.setattr(hcc, "_photos", {})
    for _ in range(2):
        r = client.get("/api/centres/2/photo")
        assert r.status_code == 200 and r.content == FakeResponse.content
        assert r.headers["content-type"] == "image/jpeg"
    assert calls == ["https://www.nea.gov.sg/images/x.jpg"]  # upgraded to https, fetched once (NFR-5)


def test_centre_photo_only_fetches_from_nea(client, monkeypatch):
    from app.controllers import hawker_centre_controller as hcc

    monkeypatch.setattr(hcc, "_photo_source", lambda db, cid: "https://evil.example.com/x.jpg")
    monkeypatch.setattr(hcc.httpx, "get", lambda *a, **k: pytest.fail("must not fetch a non-NEA URL"))
    monkeypatch.setattr(hcc, "_photos", {})
    assert client.get("/api/centres/3/photo").status_code == 404
