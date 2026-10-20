from types import SimpleNamespace as NS

from app.engineering.scoring import compute_priority, dbscan, find_duplicate, nearest_zone
from app.models import Category
from app.ai.assistant import rule_triage


def test_critical_road_beats_quiet_street():
    arterial = compute_priority("road", 50, criticality=0.95)
    alley = compute_priority("road", 50, criticality=0.05)
    assert arterial.score > alley.score
    assert arterial.sla_hours < alley.sla_hours
    assert abs(sum(b["points"] for b in arterial.breakdown.values()) - arterial.score) < 0.5


def test_confirmations_have_diminishing_returns():
    s = [compute_priority("waste", 50, 0.2, confirmations=c).score for c in (0, 1, 10, 50)]
    assert s[0] < s[1] < s[2] <= s[3]
    assert s[1] - s[0] > s[3] - s[2]


def test_duplicate_detection_radius_and_category():
    existing = NS(id="a", category=Category.waste, lat=34.74, lon=10.76, duplicate_of=None)
    assert find_duplicate("waste", 34.7402, 10.7601, [existing]) is existing   # ~25 m
    assert find_duplicate("road", 34.7402, 10.7601, [existing]) is None        # other category
    assert find_duplicate("waste", 34.745, 10.76, [existing]) is None          # ~550 m


def test_dbscan_finds_cluster_and_noise():
    pts = [(34.74, 10.76), (34.7405, 10.7605), (34.7401, 10.7598), (34.80, 10.86)]
    labels = dbscan(pts, eps_m=150, min_pts=3)
    assert labels[:3] == [0, 0, 0] and labels[3] == -1


def test_zone_lookup():
    assert nearest_zone(34.80, 10.76) == "Sakiet Ezzit"
    assert nearest_zone(34.68, 10.70) == "Thyna"


def test_rule_triage_french_and_danger():
    t = rule_triage("Un câble électrique est tombé près de l'école, des enfants passent")
    assert t["danger_to_people"] and t["suggested_urgency"] >= 80
    assert rule_triage("Énorme trou dans la chaussée")["category"] == "road"


def test_danger_to_people_is_always_critical_with_short_sla():
    p = compute_priority("lighting", 30, criticality=0.1, danger=True)
    assert p.label == "critical" and p.sla_hours <= 4
