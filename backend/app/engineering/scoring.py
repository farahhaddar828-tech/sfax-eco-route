"""Engineering decision layer.

Turns raw citizen reports into something a municipal engineer can act on:
an explainable priority score, an SLA, a cost/crew estimate, duplicate
merging, spatial hotspots and a per-road health index.

Every score returns its breakdown, so a decision can be justified ("why is
this pothole ahead of that one?") rather than being a black box.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from ..data.sfax import CATEGORIES, ZONES
from ..graph.road_graph import haversine_m

WEIGHTS = {"severity": 0.30, "citizen": 0.20, "criticality": 0.25, "crowd": 0.15, "age": 0.10}
DUPLICATE_RADIUS_M = 60
HOTSPOT_EPS_M = 250
HOTSPOT_MIN_PTS = 3


@dataclass
class Priority:
    score: float
    label: str
    sla_hours: int
    breakdown: dict
    cost_tnd: tuple[int, int]
    crew_hours: float
    service: str


def label_for(score: float) -> str:
    return "critical" if score >= 75 else "high" if score >= 55 else "medium" if score >= 35 else "low"


def compute_priority(category: str, citizen_urgency: int, criticality: float,
                     confirmations: int = 0, age_hours: float = 0.0, danger: bool = False) -> Priority:
    meta = CATEGORIES.get(category, CATEGORIES["other"])
    parts = {
        # A danger to people (live wire, fire, child at risk) overrides the category's base severity
        "severity": max(meta.severity, 1.0 if danger else 0.0),
        "citizen": max(0, min(100, citizen_urgency)) / 100,
        "criticality": max(0.0, min(1.0, criticality)),
        # diminishing returns: 1 confirmation matters, the 30th much less
        "crowd": min(1.0, math.log1p(confirmations) / math.log(11)),
        # escalates linearly until the SLA is reached
        "age": min(1.0, age_hours / meta.sla_hours) if meta.sla_hours else 0.0,
    }
    score = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)
    # A load-bearing road gets a tighter SLA (down to 50 % of the default).
    sla = max(4, int(round(meta.sla_hours * (1 - 0.5 * parts["criticality"]))))
    if danger:
        sla = min(sla, 4)
    if danger and score < 75:
        score = 75.0  # danger to people is always at least "critical"
    lo, hi = meta.cost_tnd
    factor = 1 + parts["criticality"]  # arterials need traffic management, more material
    return Priority(
        score=score, label=label_for(score), sla_hours=sla,
        breakdown={k: {"value": round(v, 3), "weight": WEIGHTS[k], "points": round(100 * WEIGHTS[k] * v, 1)}
                   for k, v in parts.items()},
        cost_tnd=(int(lo * factor), int(hi * factor)),
        crew_hours=round(meta.crew_hours * factor, 1),
        service=meta.service,
    )


def nearest_zone(lat: float, lon: float) -> str:
    return min(ZONES, key=lambda z: haversine_m(lat, lon, z.lat, z.lon)).name


def find_duplicate(category: str, lat: float, lon: float, open_reports: list) -> object | None:
    """Same category, open, within DUPLICATE_RADIUS_M -> treat as a confirmation, not a new ticket."""
    best, best_d = None, DUPLICATE_RADIUS_M
    for r in open_reports:
        if r.category.value != category or r.duplicate_of:
            continue
        d = haversine_m(lat, lon, r.lat, r.lon)
        if d <= best_d:
            best, best_d = r, d
    return best


def dbscan(points: list[tuple[float, float]], eps_m: float = HOTSPOT_EPS_M,
           min_pts: int = HOTSPOT_MIN_PTS) -> list[int]:
    """Plain DBSCAN on haversine distance. Returns a cluster id per point (-1 = noise).

    O(n^2) — fine for a few thousand open reports; swap for a PostGIS
    ST_ClusterDBSCAN query when the dataset grows.
    """
    n = len(points)
    labels = [None] * n
    neigh = [[j for j in range(n) if haversine_m(*points[i], *points[j]) <= eps_m] for i in range(n)]
    cid = -1
    for i in range(n):
        if labels[i] is not None:
            continue
        if len(neigh[i]) < min_pts:
            labels[i] = -1
            continue
        cid += 1
        labels[i] = cid
        queue = list(neigh[i])
        while queue:
            j = queue.pop()
            if labels[j] == -1:
                labels[j] = cid
            if labels[j] is not None:
                continue
            labels[j] = cid
            if len(neigh[j]) >= min_pts:
                queue.extend(neigh[j])
    return labels


def hotspots(reports: list) -> list[dict]:
    if not reports:
        return []
    labels = dbscan([(r.lat, r.lon) for r in reports])
    clusters: dict[int, list] = {}
    for r, c in zip(reports, labels):
        if c >= 0:
            clusters.setdefault(c, []).append(r)
    out = []
    for members in clusters.values():
        lat = sum(r.lat for r in members) / len(members)
        lon = sum(r.lon for r in members) / len(members)
        cats: dict[str, int] = {}
        for r in members:
            cats[r.category.value] = cats.get(r.category.value, 0) + 1
        out.append({
            "lat": lat, "lon": lon, "count": len(members),
            "zone": nearest_zone(lat, lon),
            "mean_priority": round(sum(r.priority_score for r in members) / len(members), 1),
            "categories": cats,
            "report_ids": [r.id for r in members],
        })
    return sorted(out, key=lambda h: (h["count"], h["mean_priority"]), reverse=True)


def road_health(reports: list, road_lengths_km: dict[str, float]) -> list[dict]:
    """Road Health Index (0-100) = 100 - priority-weighted open issues per km, clipped."""
    load: dict[str, float] = {}
    count: dict[str, int] = {}
    for r in reports:
        if r.road_name:
            load[r.road_name] = load.get(r.road_name, 0.0) + r.priority_score / 100
            count[r.road_name] = count.get(r.road_name, 0) + 1
    rows = []
    for name, w in load.items():
        km = max(road_lengths_km.get(name, 1.0), 0.2)
        rows.append({"road": name, "open_issues": count[name], "km": round(km, 2),
                     "health_index": round(max(0.0, 100 - 25 * w / km), 1)})
    return sorted(rows, key=lambda r: r["health_index"])


def sla_status(created_at: datetime, sla_hours: int) -> dict:
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    return {"age_hours": round(age, 1), "remaining_hours": round(sla_hours - age, 1), "breached": age > sla_hours}
