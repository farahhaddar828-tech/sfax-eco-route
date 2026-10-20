import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Category(str, enum.Enum):
    waste = "waste"            # Déchets
    road = "road"              # Routes (nids-de-poule, chaussée)
    lighting = "lighting"      # Éclairage
    traffic = "traffic"        # Circulation / feux
    school = "school"          # Abords d'écoles
    flooding = "flooding"      # Inondation / assainissement
    water = "water"            # Fuite d'eau (SONEDE)
    pollution = "pollution"    # Pollution industrielle / air
    green = "green"            # Espaces verts / arbres
    other = "other"


class Status(str, enum.Enum):
    new = "new"
    triaged = "triaged"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"
    duplicate = "duplicate"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category: Mapped[Category] = mapped_column(Enum(Category), index=True)
    description: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    zone: Mapped[str | None] = mapped_column(String(80), index=True)
    road_name: Mapped[str | None] = mapped_column(String(160))
    citizen_urgency: Mapped[int] = mapped_column(Integer, default=50)  # 0-100 slider
    photo_url: Mapped[str | None] = mapped_column(String(500))
    reporter_contact: Mapped[str | None] = mapped_column(String(160))

    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.new, index=True)
    # Engineering layer outputs
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_label: Mapped[str] = mapped_column(String(16), default="low")
    sla_hours: Mapped[int] = mapped_column(Integer, default=72)
    road_criticality: Mapped[float] = mapped_column(Float, default=0.0)
    nearest_edge: Mapped[dict | None] = mapped_column(JSON)
    duplicate_of: Mapped[str | None] = mapped_column(String(36), ForeignKey("reports.id"))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    danger: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["ReportEvent"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ReportEvent(Base):
    """Audit trail: every status change / notification is logged."""

    __tablename__ = "report_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    report: Mapped[Report] = relationship(back_populates="events")
