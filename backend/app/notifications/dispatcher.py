"""Event fan-out. The backend does not hard-code email logic: it emits a
`report.created` (or `report.escalated` / `report.resolved`) event to an n8n
webhook, and the n8n workflow decides who gets what (email to the city
inbox, Telegram for critical ones, Google Sheet log, ...).

If n8n is not configured, a direct SMTP email is sent as a fallback so the
report still reaches NOTIFY_EMAIL.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from ..config import get_settings
from ..data.sfax import CATEGORIES

log = logging.getLogger(__name__)


def build_payload(event: str, report, extra: dict | None = None) -> dict:
    s = get_settings()
    meta = CATEGORIES.get(report.category.value, CATEGORIES["other"])
    return {
        "event": event,
        "notify_email": s.notify_email,
        "report": {
            "id": report.id,
            "category": report.category.value,
            "category_label": f"{meta.emoji} {meta.label_fr}",
            "service": meta.service,
            "description": report.description,
            "zone": report.zone,
            "road_name": report.road_name,
            "lat": report.lat,
            "lon": report.lon,
            "maps_url": f"https://www.openstreetmap.org/?mlat={report.lat}&mlon={report.lon}#map=18/{report.lat}/{report.lon}",
            "citizen_urgency": report.citizen_urgency,
            "danger_to_people": bool(report.danger),
            "priority_score": report.priority_score,
            "priority_label": report.priority_label,
            "sla_hours": report.sla_hours,
            "road_criticality": report.road_criticality,
            "ai_summary": report.ai_summary,
            "photo_url": report.photo_url,
            "status": report.status.value,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        },
        **(extra or {}),
    }


async def dispatch(event: str, report, extra: dict | None = None) -> str:
    """Returns the channel used: 'n8n', 'smtp' or 'none'."""
    s = get_settings()
    payload = build_payload(event, report, extra)
    if s.n8n_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(s.n8n_webhook_url, json=payload)
                r.raise_for_status()
            return "n8n"
        except httpx.HTTPError as e:
            log.warning("n8n webhook failed (%s), falling back to SMTP", e)
    if s.smtp_host:
        try:
            _send_smtp(payload)
            return "smtp"
        except Exception as e:  # noqa: BLE001 - notification must never break report intake
            log.error("SMTP fallback failed: %s", e)
    return "none"


def _send_smtp(payload: dict) -> None:
    s = get_settings()
    r = payload["report"]
    msg = EmailMessage()
    msg["Subject"] = f"[Eco-Route][{r['priority_label'].upper()}] {r['category_label']} – {r['zone']}"
    msg["From"] = s.smtp_user
    msg["To"] = s.notify_email
    msg.set_content(
        f"Nouveau signalement ({payload['event']})\n\n"
        f"Catégorie : {r['category_label']}\nService : {r['service']}\n"
        f"Zone : {r['zone']} — {r['road_name'] or ''}\n"
        f"Priorité : {r['priority_score']}/100 ({r['priority_label']}), SLA {r['sla_hours']} h\n\n"
        f"{r['description']}\n\nRésumé IA : {r['ai_summary'] or '-'}\n\nCarte : {r['maps_url']}\n"
    )
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)
