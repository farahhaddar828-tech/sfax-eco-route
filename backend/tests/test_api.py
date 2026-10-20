def _post(client, **kw):
    body = {"description": "Tas de déchets qui brûle", "lat": 34.7406, "lon": 10.7603, "citizen_urgency": 60}
    body.update(kw)
    r = client.post("/api/v1/reports", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["graph"] == "demo"


def test_create_report_is_triaged_scored_and_snapped(client):
    rep = _post(client, description="Gros trou dans la chaussée, dangereux pour les motos",
                lat=34.7700, lon=10.7650)
    assert rep["category"] == "road"                     # AI/rules triage chose it
    assert rep["road_name"]                               # snapped to a graph edge
    assert 0 < rep["priority_score"] <= 100
    assert rep["responsible_service"]
    assert set(rep["priority_breakdown"]) == {"severity", "citizen", "criticality", "crowd", "age"}


def test_duplicate_is_merged(client):
    a = _post(client, category="waste", lat=34.7300, lon=10.7400)
    b = _post(client, category="waste", lat=34.7301, lon=10.7401, description="encore des ordures ici")
    assert b["merged_into_existing"] and b["id"] == a["id"] and b["upvotes"] == 1


def test_dashboard_hotspots_and_road_health(client):
    for i in range(3):
        _post(client, category="lighting", lat=34.7500 + i * 0.0010, lon=10.7200, description=f"lampadaire {i}")
    d = client.get("/api/v1/analytics/dashboard").json()
    assert d["open"] >= 4 and "by_category" in d
    hs = client.get("/api/v1/analytics/hotspots").json()
    assert any(h["count"] >= 3 for h in hs)
    assert client.get("/api/v1/analytics/road-health").json()


def test_graph_endpoints(client):
    assert client.get("/api/v1/graph/stats").json()["nodes"] > 50
    assert client.get("/api/v1/graph/roads?q=route").json()["count"] >= 11
    imp = client.get("/api/v1/graph/closure-impact", params={"lat": 34.77, "lon": 10.765, "samples": 20}).json()
    assert "sampled_trips_affected_pct" in imp
    route = client.post("/api/v1/graph/route", json={"origin": [34.80, 10.76], "destination": [34.70, 10.72]}).json()
    assert route["eco_route"]["length_m"] > 0
    tour = client.post("/api/v1/graph/crew-tour", json={"max_stops": 5}).json()
    assert len(tour["stops"]) >= 2


def test_status_flow_and_sla(client):
    rep = _post(client, category="water", lat=34.7900, lon=10.8600, description="fuite d'eau SONEDE")
    r = client.patch(f"/api/v1/reports/{rep['id']}/status", json={"status": "resolved", "note": "réparé"})
    assert r.json()["status"] == "resolved"
    detail = client.get(f"/api/v1/reports/{rep['id']}").json()
    assert any(e["kind"] == "status:resolved" for e in detail["events"])
    assert client.get("/api/v1/analytics/dashboard").json()["mean_time_to_resolve_h"] is not None


def test_assistant_without_llm_gives_safety_first(client):
    r = client.post("/api/v1/assistant/chat", json={
        "messages": [{"role": "user", "content": "Il y a un câble électrique par terre sur la route de Tunis"}],
        "lat": 34.76, "lon": 10.76}).json()
    assert "10 m" in r["reply"] and r["provider"] == "none"


def test_open311(client):
    assert any(s["service_code"] == "road" for s in client.get("/open311/v2/services.json").json())
    r = client.post("/open311/v2/requests.json", data={"service_code": "green", "lat": 34.75, "long": 10.73,
                                                       "description": "arbre tombé"})
    assert r.status_code == 200 and r.json()[0]["service_request_id"]
    assert client.get("/open311/v2/requests.json").json()


def test_metrics_exposed(client):
    assert "ecoroute_reports_created_total" in client.get("/metrics").text


def test_fallen_cable_near_school_is_critical(client):
    rep = _post(client, description="Un câble électrique est tombé sur la chaussée devant le lycée",
                lat=34.7712, lon=10.7651, citizen_urgency=40)
    assert rep["danger"] and rep["priority_label"] == "critical" and rep["sla_hours"] <= 4
    assert rep["category"] == "lighting"
