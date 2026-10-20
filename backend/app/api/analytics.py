from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..data.sfax import CATEGORIES, ZONES
from ..db import get_db
from ..engineering.scoring import hotspots, road_health, sla_status
from ..graph.road_graph import get_graph
from ..metrics import OPEN_REPORTS, SLA_BREACHED
from ..models import Report, Status

router = APIRouter(prefix="/analytics", tags=["analytics"])
OPEN = [Status.new, Status.triaged, Status.assigned, Status.in_progress]


def _open(db: Session) -> list[Report]:
    return db.query(Report).filter(Report.status.in_(OPEN), Report.duplicate_of.is_(None)).all()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    all_r = db.query(Report).filter(Report.duplicate_of.is_(None)).all()
    open_r = [r for r in all_r if r.status in OPEN]
    resolved = [r for r in all_r if r.status == Status.resolved and r.resolved_at]
    breached = [r for r in open_r if sla_status(r.created_at, r.sla_hours)["breached"]]
    by_label = Counter(r.priority_label for r in open_r)
    for lbl in ("low", "medium", "high", "critical"):
        OPEN_REPORTS.labels(priority=lbl).set(by_label.get(lbl, 0))
    SLA_BREACHED.set(len(breached))

    def mttr_h():
        def naive(d):  # SQLite drops tz; Postgres keeps it
            return d.replace(tzinfo=None)

        hrs = [(naive(r.resolved_at) - naive(r.created_at)).total_seconds() / 3600 for r in resolved]
        return round(sum(hrs) / len(hrs), 1) if hrs else None

    return {
        "total": len(all_r),
        "open": len(open_r),
        "urgent": by_label.get("high", 0) + by_label.get("critical", 0),
        "urgent_rate_pct": round(100 * (by_label.get("high", 0) + by_label.get("critical", 0)) / len(open_r), 1) if open_r else 0,
        "resolved": len(resolved),
        "sla_breached": len(breached),
        "mean_time_to_resolve_h": mttr_h(),
        "by_priority": dict(by_label),
        "by_category": {k: {"label": f"{CATEGORIES[k].emoji} {CATEGORIES[k].label_fr}", "count": v}
                        for k, v in Counter(r.category.value for r in open_r).items()},
        "by_zone": dict(Counter(r.zone for r in open_r).most_common()),
        "by_service": dict(Counter(CATEGORIES[r.category.value].service for r in open_r).most_common()),
    }


@router.get("/hotspots")
def get_hotspots(db: Session = Depends(get_db)):
    return hotspots(_open(db))


@router.get("/road-health")
def get_road_health(db: Session = Depends(get_db)):
    g = get_graph()
    lengths: dict[str, float] = {}
    for *_, d in g.g.edges(data=True):
        if d.get("name"):
            lengths[d["name"]] = lengths.get(d["name"], 0.0) + d["length"] / 1000
    return road_health(_open(db), lengths)


@router.get("/zones")
def zones():
    return [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in ZONES]


@router.get("/categories")
def categories():
    return {k: {"label": m.label_fr, "emoji": m.emoji, "service": m.service, "sla_hours": m.sla_hours}
            for k, m in CATEGORIES.items()}


@router.get("/sla-breaches")
def sla_breaches(db: Session = Depends(get_db)):
    rows = []
    for r in _open(db):
        s = sla_status(r.created_at, r.sla_hours)
        if s["breached"]:
            rows.append({"id": r.id, "category": r.category.value, "road": r.road_name,
                         "service": CATEGORIES[r.category.value].service, **s})
    return sorted(rows, key=lambda x: x["remaining_hours"])
