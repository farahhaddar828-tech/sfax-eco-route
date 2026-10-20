"""Regression tests for defects found by adversarial probing of the live API.

Each of these returned the wrong thing before the fix:

* an unknown Open311 `service_code` raised ValueError and returned 500, because
  that path builds the Category enum by hand instead of through Pydantic;
* a description containing a NUL byte was stored, which SQLite accepts and
  PostgreSQL rejects outright, so the suite passed while production would 500;
* a whitespace-only description passed `min_length=3` and created a blank report;
* `critical-edges?top=0` and `top=-5` were accepted and sliced the list backwards.
"""


def test_open311_rejects_unknown_service_code(client):
    r = client.post(
        "/open311/v2/requests.json",
        data={"service_code": "volcano", "lat": 34.74, "long": 10.76,
              "description": "service code qui n'existe pas"},
    )
    assert r.status_code == 400, r.text
    assert "volcano" in r.text


def test_open311_still_accepts_a_known_service_code(client):
    r = client.post(
        "/open311/v2/requests.json",
        data={"service_code": "waste", "lat": 34.7955, "long": 10.7100,
              "description": "Ordures entassees pres du marche"},
    )
    assert r.status_code == 200, r.text
    assert r.json()[0]["service_request_id"]


def test_nul_byte_is_stripped_from_the_description(client):
    """PostgreSQL cannot store NUL in a text column; strip it before it gets there."""
    r = client.post("/api/v1/reports", json={
        "description": "Fuite\x00 d eau sur la chaussee", "lat": 34.7960, "lon": 10.7105})
    assert r.status_code == 201, r.text
    assert "\x00" not in r.json()["description"]


def test_whitespace_only_description_is_refused(client):
    r = client.post("/api/v1/reports", json={
        "description": "        ", "lat": 34.7965, "lon": 10.7110})
    assert r.status_code == 422, r.text


def test_description_is_trimmed(client):
    r = client.post("/api/v1/reports", json={
        "description": "   Lampadaire casse depuis une semaine   ", "lat": 34.7970, "lon": 10.7115})
    assert r.status_code == 201, r.text
    assert r.json()["description"] == "Lampadaire casse depuis une semaine"


def test_critical_edges_rejects_a_non_positive_top(client):
    for bad in (0, -5):
        r = client.get(f"/api/v1/graph/critical-edges?top={bad}")
        assert r.status_code == 422, f"top={bad} returned {r.status_code}"


def test_critical_edges_still_honours_a_valid_top(client):
    r = client.get("/api/v1/graph/critical-edges?top=3")
    assert r.status_code == 200
    assert len(r.json()) <= 3
