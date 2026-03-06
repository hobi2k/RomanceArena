from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import traceback
from fastapi import FastAPI, HTTPException

from .schemas import StartRequest, StartResponse, TurnRequest, TurnResponse
from .service import DateWithSayaService


svc = DateWithSayaService()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 동기 preload: 서버가 뜨기 전에 모델/파이프라인을 확실히 준비한다.
    svc.preload()
    yield


app = FastAPI(title="Date With Saya Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    if svc.ready:
        return {"status": "ok"}
    return {"status": "not_ok", "error": svc.startup_error or "preloading"}


@app.post("/start", response_model=StartResponse)
def start(req: StartRequest) -> StartResponse:
    try:
        s = svc.start(session_id=req.session_id, npc_id=req.npc_id)
    except Exception as e:
        logger.error("start failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"start failed: {e}")
    return StartResponse(session_id=s.session_id, npc_id=s.npc_id, status="started")


@app.post("/turn", response_model=TurnResponse)
def turn(req: TurnRequest) -> TurnResponse:
    try:
        result = svc.run_turn(
            req.session_id,
            req.player_action,
            req.player_text,
            player_name=req.player_name,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    except Exception as e:
        logger.error("turn failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"turn failed: {e}")
    return TurnResponse(**result)
