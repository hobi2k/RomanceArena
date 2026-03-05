from __future__ import annotations

"""FastAPI HTTP 인터페이스.

이 모듈은 in-memory 세션 사전을 사용해 게임 엔진 인스턴스를 관리한다.
단일 프로세스/개발용 실행을 전제로 하며, 멀티 워커 배포 시 외부 세션 저장소가 필요하다.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import RomanceArenaEngine
from .models import Action
from .npc.configs import NPCS


app = FastAPI(title="Romance Arena API", version="0.1.0")

SESSIONS: dict[str, RomanceArenaEngine] = {}


class StartRequest(BaseModel):
    """세션 시작 요청."""

    npc_id: str = Field(description="one of: saya, mai")
    session_id: str


class TurnRequest(BaseModel):
    """턴 진행 요청."""

    session_id: str
    player_action: Action


@app.get("/health")
def health() -> dict:
    """헬스체크 엔드포인트."""
    return {"status": "ok"}


@app.get("/npcs")
def list_npcs() -> dict:
    """선택 가능한 NPC 목록을 반환한다."""
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
    """세션을 생성하고 초기 상태/행동 공간을 반환한다."""
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
    """지정 세션에서 1턴을 실행하고 결과를 반환한다."""
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
    """세션 장기기억 목록을 조회한다."""
    engine = SESSIONS.get(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "long_term_memory": engine.memory.list_long_term(session_id),
    }
