from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..graph.road_graph import get_graph
from ..models import Report, Status
from ..schemas import CrewRequest, RouteRequest

router = APIRouter(prefix="/graph", tags=["graph & routing"])
OPEN = [Status.new, Status.triaged, Status.assigned, Status.in_progress]


def hazards_from_db(db: Session) -> list[tuple[tuple, float]]:
    """Open reports -> (edge, severity) pairs used as routing penalties."""
    out = []
    for r in db.query(Report).filter(Report.status.in_(OPEN), Report.duplicate_of.is_(None)).all():
        if r.nearest_edge:
            out.append(((r.nearest_edge["u"], r.nearest_edge["v"]), r.priority_score / 100))
    return out


@router.get("/stats")
def stats():
    return get_graph().stats()


@router.get("/roads")
def roads(q: str | None = None, limit: int = Query(50, le=2000)):
    """Every named road in the network — the v1 app only knew 8."""
    names = get_graph().road_names()
    if q:
        names = [n for n in names if q.lower() in n.lower()]
    return {"count": len(names), "roads": names[:limit]}


@router.get("/critical-edges")
def critical_edges(top: int = Query(15, ge=1, le=100)):
    return get_graph().most_critical_edges(top)


@router.get("/edge-at")
def edge_at(lat: float, lon: float):
    g = get_graph()
    return g.edge_info(*g.nearest_edge(lat, lon))


@router.get("/closure-impact")
def closure_impact(lat: float, lon: float, samples: int = Query(60, le=300)):
    g = get_graph()
    u, v = g.nearest_edge(lat, lon)
    return g.closure_impact(u, v, samples=samples)


@router.post("/route")
def route(body: RouteRequest, db: Session = Depends(get_db)):
    return get_graph().route(body.origin, body.destination, hazards_from_db(db), body.avoid_strength)


@router.post("/crew-tour")
def crew_tour(body: CrewRequest, db: Session = Depends(get_db)):
    from ..data.sfax import CATEGORIES
    q = db.query(Report).filter(Report.status.in_(OPEN), Report.duplicate_of.is_(None))
    if body.report_ids:
        reports = q.filter(Report.id.in_(body.report_ids)).all()
    else:
        reports = q.order_by(Report.priority_score.desc()).all()
        if body.service:
            reports = [r for r in reports if CATEGORIES[r.category.value].service == body.service]
        reports = reports[: body.max_stops]
    if not reports:
        raise HTTPException(404, "no open reports to visit")
    tour = get_graph().crew_tour(body.depot, [(r.lat, r.lon) for r in reports])
    tour["stops"] = [{"order": i + 1, "id": reports[j].id, "category": reports[j].category.value,
                      "road": reports[j].road_name, "priority": reports[j].priority_score}
                     for i, j in enumerate(tour["visit_order"])]
    return tour
