"""FastAPI app: static UI + JSON API. Run: uvicorn saathi.api:app --reload"""
from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .engine import Profile, find_schemes, load_schemes

log = logging.getLogger("saathi")
STATIC = Path(__file__).parent / "static"
MAX_SESSIONS = 200

app = FastAPI(title="Sarkari Saathi", version="0.1.0")
_sessions: "OrderedDict[str, Any]" = OrderedDict()


class ProfileIn(BaseModel):
    age: int | None = Field(None, ge=0, le=120)
    gender: str | None = None
    occupation: str | None = None
    annual_family_income: int | None = Field(None, ge=0)
    social_category: str | None = None
    owns_land: bool | None = None
    owns_pucca_house: bool | None = None
    is_bpl: bool | None = None
    has_bank_account: bool | None = None
    has_girl_child_under_10: bool | None = None
    is_student: bool | None = None
    wants_business: bool | None = None


class ChatIn(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=1000)


def _agent_for(session_id: str) -> Any:
    from .agent import build_agent  # lazy: the form works even if no model is configured

    if session_id in _sessions:
        _sessions.move_to_end(session_id)
        return _sessions[session_id]
    if len(_sessions) >= MAX_SESSIONS:
        _sessions.popitem(last=False)
    _sessions[session_id] = build_agent()
    return _sessions[session_id]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/schemes")
def schemes() -> dict[str, Any]:
    return load_schemes()


@app.post("/api/eligibility")
def eligibility(body: ProfileIn) -> dict[str, Any]:
    return find_schemes(Profile.from_dict(body.model_dump()))


@app.post("/api/chat")
def chat(body: ChatIn) -> dict[str, str]:
    try:
        reply = str(_agent_for(body.session_id)(body.message))
    except Exception as exc:  # model down / no key: degrade gracefully
        log.exception("chat failed")  # full cause is printed in the server terminal
        raise HTTPException(
            status_code=503,
            detail=f"AI assistant unavailable ({type(exc).__name__}). Use the form instead, or check MODEL_PROVIDER / MODEL_ID / API key in .env (details in the server terminal).",
        ) from exc
    return {"reply": reply}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
