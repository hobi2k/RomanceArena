from __future__ import annotations

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    session_id: str
    npc_id: str = Field(default="saya")


class StartResponse(BaseModel):
    session_id: str
    npc_id: str
    status: str


class TurnRequest(BaseModel):
    session_id: str
    player_action: str
    player_text: str = ""
    player_name: str = "플레이어"


class TurnResponse(BaseModel):
    session_id: str
    player_action: str
    player_text: str
    saya_text: str
    saya_narration: str
    saya_dialogue: str
    emotion: str
    image_key: str
    player_options: list[str]
    translated_dialogue: str
    wav_path: str | None
