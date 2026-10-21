from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Category, Status


class ReportCreate(BaseModel):
    category: Category | None = None          # None -> AI triage decides
    description: str = Field(min_length=3, max_length=2000)
    lat: float = Field(ge=34.5, le=35.0)      # Grand Sfax bounding box
    lon: float = Field(ge=10.4, le=11.0)
    citizen_urgency: int = Field(50, ge=0, le=100)
    photo_url: str | None = None
    reporter_contact: str | None = None

    @field_validator("description")
    @classmethod
    def _clean_description(cls, v: str) -> str:
        """Strip NUL bytes and blank padding.

        PostgreSQL cannot store NUL in a text column while SQLite accepts it, so
        without this the test suite passes and production returns 500. Stripping
        also rejects whitespace-only descriptions, which `min_length` lets through.
        """
        v = v.replace("\x00", "").strip()
        if len(v) < 3:
            raise ValueError("description must hold at least 3 non-blank characters")
        return v


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: Category
    description: str
    lat: float
    lon: float
    zone: str | None
    road_name: str | None
    citizen_urgency: int
    photo_url: str | None
    status: Status
    priority_score: float
    priority_label: str
    sla_hours: int
    road_criticality: float
    duplicate_of: str | None
    ai_summary: str | None
    upvotes: int
    danger: bool = False
    created_at: datetime


class ReportCreated(ReportOut):
    merged_into_existing: bool = False
    notification_channel: str = "none"
    priority_breakdown: dict | None = None
    cost_estimate_tnd: tuple[int, int] | None = None
    responsible_service: str | None = None


class StatusUpdate(BaseModel):
    status: Status
    note: str | None = None


class RouteRequest(BaseModel):
    origin: tuple[float, float]
    destination: tuple[float, float]
    avoid_strength: float = Field(4.0, ge=0, le=20)


class CrewRequest(BaseModel):
    depot: tuple[float, float] = (34.7406, 10.7603)
    report_ids: list[str] | None = None   # None -> top open reports of `service`
    service: str | None = None
    max_stops: int = Field(10, ge=1, le=25)


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    lat: float | None = None
    lon: float | None = None
    # UI language chosen in Settings: pins the reply language instead of letting
    # the model guess from the question.
    lang: str | None = Field(None, max_length=8)


class TriageRequest(BaseModel):
    text: str
