from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai import assistant
from ..ai.llm import LLM
from ..db import get_db
from ..metrics import ASSISTANT_CALLS
from ..schemas import ChatRequest, TriageRequest

router = APIRouter(prefix="/assistant", tags=["ai assistant"])


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    pos = (body.lat, body.lon) if body.lat is not None and body.lon is not None else None
    res = await assistant.ask(db, [m.model_dump() for m in body.messages[-12:]], pos, body.lang)
    ASSISTANT_CALLS.labels(provider=res.provider).inc()
    draft = next((t["args"] for t in res.tool_trace if t["tool"] == "draft_report"), None)
    return {"reply": res.text, "tools_used": [t["tool"] for t in res.tool_trace],
            "report_draft": draft, "provider": res.provider, "model": res.model}


@router.post("/triage")
async def triage(body: TriageRequest):
    return await assistant.triage(body.text)


@router.get("/provider")
def provider():
    llm = LLM()
    return {"provider": llm.provider, "model": llm.model, "enabled": llm.enabled}
