from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import RomanceArenaEngine
from .models import Action
from .npc.configs import NPCS


app = FastAPI(title="Romance Arena API", version="0.1.0")

SESSIONS: dict[str, RomanceArenaEngine] = {}


class StartRequest(BaseModel):
    npc_id: str = Field(description="one of: saya, mai")
    session_id: str


class TurnRequest(BaseModel):
    session_id: str
    player_action: Action


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/npcs")
def list_npcs() -> dict:
    return {
        "npcs": [
            {
                "npc_id": npc.npc_id,
                "name": npc.name,
                "personality": npc.personality,
                "scenario": npc.scenario,
                "persona": npc.persona,
            }
            for npc in NPCS.values()
        ]
    }


@app.post("/start")
def start(req: StartRequest) -> dict:
    profile = NPCS.get(req.npc_id)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"unknown npc_id: {req.npc_id}")
    SESSIONS[req.session_id] = RomanceArenaEngine(profile, session_id=req.session_id)
    return {
        "session_id": req.session_id,
        "npc_id": req.npc_id,
        "npc_name": profile.name,
        "player_actions": [a.value for a in profile.player_actions],
        "npc_actions": [a.value for a in profile.npc_actions],
        "state": SESSIONS[req.session_id].env.snapshot(),
    }


@app.post("/turn")
def turn(req: TurnRequest) -> dict:
    engine = SESSIONS.get(req.session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.step(req.player_action)
    return {
        "turn": engine.session.turn,
        "player_action": result.player_action.value,
        "npc_action": result.npc_action.value,
        "player_turn_text": result.player_turn_text,
        "npc_turn_text": result.npc_turn_text,
        "npc_dialogue": result.npc_dialogue,
        "reason": result.reason,
        "state": engine.env.snapshot(),
        "events": result.events,
        "outcome": result.outcome,
    }


@app.get("/memory/{session_id}")
def memory(session_id: str) -> dict:
    engine = SESSIONS.get(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "long_term_memory": engine.memory.list_long_term(session_id),
    }
