import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..ai.assistant import triage
from ..db import SessionLocal, get_db
from ..engineering.scoring import compute_priority, find_duplicate, nearest_zone, sla_status
from ..graph.road_graph import get_graph
from ..models import Category, Report, ReportEvent, Status
from ..notifications.dispatcher import dispatch
from ..schemas import ReportCreate, ReportCreated, ReportOut, StatusUpdate
from ..metrics import REPORTS_CREATED

router = APIRouter(prefix="/reports", tags=["reports"])
OPEN = [Status.new, Status.triaged, Status.assigned, Status.in_progress]
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")


def rescore(r: Report) -> dict:
    age = (datetime.now(timezone.utc) - (r.created_at if r.created_at.tzinfo
                                         else r.created_at.replace(tzinfo=timezone.utc))).total_seconds() / 3600
    p = compute_priority(r.category.value, r.citizen_urgency, r.road_criticality, r.upvotes, age, bool(r.danger))
    r.priority_score, r.priority_label, r.sla_hours = p.score, p.label, p.sla_hours
    return {"breakdown": p.breakdown, "cost": p.cost_tnd, "service": p.service}


async def _notify(report_id: str, event: str) -> None:
    db = SessionLocal()
    try:
        r = db.get(Report, report_id)
        channel = await dispatch(event, r)
        db.add(ReportEvent(report_id=r.id, kind=f"notify:{event}", detail=channel))
        db.commit()
    finally:
        db.close()


@router.post("", response_model=ReportCreated, status_code=201)
async def create_report(body: ReportCreate, bg: BackgroundTasks, db: Session = Depends(get_db)):
    tri = await triage(body.description)
    category = body.category or Category(tri["category"])
    graph = get_graph()
    u, v = graph.nearest_edge(body.lat, body.lon)
    edge = graph.edge_info(u, v)

    open_reports = db.query(Report).filter(Report.status.in_(OPEN)).all()
    dup = find_duplicate(category.value, body.lat, body.lon, open_reports)
    if dup:  # merge: the existing ticket gains a confirmation and its priority rises
        dup.upvotes += 1
        dup.citizen_urgency = max(dup.citizen_urgency, body.citizen_urgency)
        dup.danger = bool(dup.danger) or bool(tri.get("danger_to_people"))
        extra = rescore(dup)
        db.add(ReportEvent(report_id=dup.id, kind="confirmation", detail=body.description[:300]))
        db.commit()
        REPORTS_CREATED.labels(category=category.value, merged="true").inc()
        return ReportCreated(**ReportOut.model_validate(dup).model_dump(), merged_into_existing=True,
                             priority_breakdown=extra["breakdown"], cost_estimate_tnd=extra["cost"],
                             responsible_service=extra["service"])

    r = Report(
        category=category, description=body.description, lat=body.lat, lon=body.lon,
        zone=nearest_zone(body.lat, body.lon), road_name=edge["name"],
        citizen_urgency=body.citizen_urgency, photo_url=body.photo_url,
        reporter_contact=body.reporter_contact, road_criticality=edge["criticality"],
        nearest_edge={"u": edge["u"], "v": edge["v"]}, ai_summary=tri.get("summary"),
        status=Status.triaged, created_at=datetime.now(timezone.utc), upvotes=0,
        danger=bool(tri.get("danger_to_people")),
    )
    extra = rescore(r)
    db.add(r)
    db.add(ReportEvent(report=r, kind="created", detail=f"triage={tri.get('engine')}"))
    db.commit()
    REPORTS_CREATED.labels(category=category.value, merged="false").inc()
    bg.add_task(_notify, r.id, "report.created")
    return ReportCreated(**ReportOut.model_validate(r).model_dump(), notification_channel="queued",
                         priority_breakdown=extra["breakdown"], cost_estimate_tnd=extra["cost"],
                         responsible_service=extra["service"])


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db), status: Status | None = None, category: Category | None = None,
                 zone: str | None = None, open_only: bool = False, limit: int = Query(100, le=500)):
    q = db.query(Report).filter(Report.duplicate_of.is_(None))
    if status:
        q = q.filter(Report.status == status)
    if open_only:
        q = q.filter(Report.status.in_(OPEN))
    if category:
        q = q.filter(Report.category == category)
    if zone:
        q = q.filter(Report.zone == zone)
    return q.order_by(Report.created_at.desc()).limit(limit).all()


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "report not found")
    return {**ReportOut.model_validate(r).model_dump(), "sla": sla_status(r.created_at, r.sla_hours),
            "events": [{"kind": e.kind, "detail": e.detail, "at": e.created_at} for e in r.events]}


@router.post("/{report_id}/upvote", response_model=ReportOut)
def upvote(report_id: str, db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "report not found")
    r.upvotes += 1
    rescore(r)
    db.commit()
    return r


@router.patch("/{report_id}/status", response_model=ReportOut)
async def update_status(report_id: str, body: StatusUpdate, bg: BackgroundTasks, db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "report not found")
    r.status = body.status
    if body.status == Status.resolved:
        r.resolved_at = datetime.now(timezone.utc)
    db.add(ReportEvent(report_id=r.id, kind=f"status:{body.status.value}", detail=body.note))
    db.commit()
    if body.status == Status.resolved:
        bg.add_task(_notify, r.id, "report.resolved")
    return r


@router.post("/photos", tags=["reports"])
async def upload_photo(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "image required")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "max 8 MB")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4()}.{file.content_type.split('/')[1]}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return {"photo_url": f"/uploads/{name}"}
