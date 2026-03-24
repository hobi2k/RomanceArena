from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import traceback
from fastapi import FastAPI, HTTPException

from .runtime import VLLMRuntimeManager
from .schemas import (
    SessionDiscardRequest,
    SessionOpResponse,
    SessionSaveRequest,
    StartRequest,
    StartResponse,
    TurnRequest,
    TurnResponse,
)
from .service import DateWithSayaService


svc = DateWithSayaService()
runtime = VLLMRuntimeManager()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """앱 수명주기 훅.

    Args:
        _app: FastAPI 앱 인스턴스.

    Returns:
        None. 컨텍스트 진입 시 preload를 수행하고, 종료 시점을 호출자에 위임한다.
    """
    # 배포 기준: 로컬 Kanana 런타임 검증과 서비스 preload를 백엔드에서 관리한다.
    runtime.start()
    svc.preload()
    yield
    runtime.stop()


app = FastAPI(title="Date With Saya Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """백엔드 상태를 반환한다.

    Args:
        없음.

    Returns:
        dict: 준비 완료 시 `{"status":"ok"}`, 미완료 시 에러 정보를 포함한 `not_ok`.
    """
    if svc.ready:
        return {"status": "ok", "memory": svc.memory_status()}
    return {"status": "not_ok", "error": svc.startup_error or "preloading"}


@app.post("/start", response_model=StartResponse)
def start(req: StartRequest) -> StartResponse:
    """세션을 시작한다.

    Args:
        req: 세션 ID와 NPC ID를 포함한 시작 요청.

    Returns:
        StartResponse: 세션 시작 결과.
    """
    try:
        s = svc.start(session_id=req.session_id, npc_id=req.npc_id)
    except Exception as e:
        logger.error("start failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"start failed: {e}")
    return StartResponse(session_id=s.session_id, npc_id=s.npc_id, status="started")


@app.post("/turn", response_model=TurnResponse)
def turn(req: TurnRequest) -> TurnResponse:
    """한 턴을 처리한다.

    Args:
        req: 플레이어 행동/텍스트/이름을 포함한 턴 요청.

    Returns:
        TurnResponse: 사야 응답, 감정, 선택지 등을 포함한 턴 결과.
    """
    try:
        result = svc.run_turn(
            req.session_id,
            req.player_action,
            req.player_text,
            player_name=req.player_name,
            player_love=req.player_love,
            player_rel=req.player_rel,
            player_charm=req.player_charm,
            player_intel=req.player_intel,
            player_create=req.player_create,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    except Exception as e:
        logger.error("turn failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"turn failed: {e}")
    return TurnResponse(**result)


@app.post("/session/save", response_model=SessionOpResponse)
def session_save(req: SessionSaveRequest) -> SessionOpResponse:
    """세션을 저장 완료 상태로 마킹한다.

    Args:
        req: 세션 저장 요청.

    Returns:
        SessionOpResponse: 저장 마킹 결과.
    """
    ok = svc.mark_session_saved(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionOpResponse(ok=True, detail="session saved")


@app.post("/session/discard", response_model=SessionOpResponse)
def session_discard(req: SessionDiscardRequest) -> SessionOpResponse:
    """세션을 폐기한다.

    Args:
        req: 세션 폐기 요청.

    Returns:
        SessionOpResponse: 폐기 결과.
    """
    ok = svc.discard_session(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionOpResponse(ok=True, detail="session discarded")
