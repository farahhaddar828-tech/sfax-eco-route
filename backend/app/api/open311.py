"""Open311 GeoReport v2 compatibility layer.

Open311 is the open standard used by FixMyStreet, SeeClickFix and many
city 311 systems. Exposing it means any Open311 client or city back-office
can read and submit Eco-Route reports without custom integration.
Spec: https://wiki.open311.org/GeoReport_v2
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Form
from sqlalchemy.orm import Session

from ..data.sfax import CATEGORIES
from ..db import get_db
from ..models import Category, Report, Status
from ..schemas import ReportCreate
from .reports import create_report

router = APIRouter(prefix="/open311/v2", tags=["open311"])
STATUS_MAP = {Status.resolved: "closed", Status.rejected: "closed", Status.duplicate: "closed"}


@router.get("/services.json")
def services():
    return [{"service_code": k, "service_name": m.label_fr, "description": m.service,
             "metadata": False, "type": "realtime", "keywords": k, "group": m.service}
            for k, m in CATEGORIES.items()]


def _to311(r: Report) -> dict:
    return {"service_request_id": r.id, "status": STATUS_MAP.get(r.status, "open"),
            "service_code": r.category.value, "service_name": CATEGORIES[r.category.value].label_fr,
            "description": r.description, "agency_responsible": CATEGORIES[r.category.value].service,
            "requested_datetime": r.created_at.isoformat(), "updated_datetime": r.updated_at.isoformat() if r.updated_at else None,
            "address": f"{r.road_name or ''}, {r.zone or ''}, Sfax", "lat": r.lat, "long": r.lon,
            "media_url": r.photo_url}


@router.get("/requests.json")
def requests(db: Session = Depends(get_db), status: str | None = None):
    rows = db.query(Report).filter(Report.duplicate_of.is_(None)).order_by(Report.created_at.desc()).limit(1000).all()
    out = [_to311(r) for r in rows]
    return [o for o in out if not status or o["status"] == status]


@router.post("/requests.json")
async def post_request(bg: BackgroundTasks, service_code: str = Form(...), lat: float = Form(...),
                       long: float = Form(...), description: str = Form(...), media_url: str | None = Form(None),
                       db: Session = Depends(get_db)):
    created = await create_report(ReportCreate(category=Category(service_code), description=description,
                                               lat=lat, lon=long, photo_url=media_url), bg, db)
    return [{"service_request_id": created.id, "service_notice": created.responsible_service}]
