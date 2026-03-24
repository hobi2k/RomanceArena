from __future__ import annotations

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    """세션 시작 요청 스키마.

    Args:
        session_id: 세션 식별자.
        npc_id: 대화 대상 NPC 식별자.

    Returns:
        StartRequest: 유효성 검증이 완료된 요청 객체.
    """
    session_id: str
    npc_id: str = Field(default="saya")


class StartResponse(BaseModel):
    """세션 시작 응답 스키마.

    Args:
        session_id: 생성 또는 확인된 세션 식별자.
        npc_id: 선택된 NPC 식별자.
        status: 시작 상태 문자열.

    Returns:
        StartResponse: 직렬화 가능한 응답 객체.
    """
    session_id: str
    npc_id: str
    status: str


class TurnRequest(BaseModel):
    """턴 처리 요청 스키마.

    Args:
        session_id: 현재 세션 식별자.
        player_action: 플레이어 행동 타입.
        player_text: 플레이어가 실제 입력한 텍스트.
        player_name: Ren'Py에서 지정한 플레이어 이름.

    Returns:
        TurnRequest: 유효성 검증이 완료된 요청 객체.
    """
    session_id: str
    player_action: str
    player_text: str = ""
    player_name: str = "플레이어"
    player_love: int = 0
    player_rel: str = "Stranger"
    player_charm: int = 0
    player_intel: int = 0
    player_create: int = 0


class TurnResponse(BaseModel):
    """턴 처리 응답 스키마.

    Args:
        session_id: 세션 식별자.
        player_action: 처리된 플레이어 행동.
        player_text: 처리된 플레이어 텍스트.
        saya_text: 원문 RP 출력.
        saya_narration: 파싱된 서술 블록.
        saya_dialogue: 파싱된 대사 블록.
        emotion: 감정 라벨.
        image_key: 표정 이미지 키.
        player_options: 다음 플레이어 선택지 3개.
        translated_dialogue: 번역(또는 동일) 대사.
        wav_path: 음성 파일 경로(미생성 시 None).

    Returns:
        TurnResponse: 직렬화 가능한 응답 객체.
    """
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
    action_result: str
    date_accepted: bool
    affection_delta: int
    saya_fsm_state: str


class SessionSaveRequest(BaseModel):
    """세션 저장 요청 스키마.

    Args:
        session_id: 저장할 세션 식별자.

    Returns:
        SessionSaveRequest: 유효성 검증이 완료된 요청 객체.
    """

    session_id: str


class SessionDiscardRequest(BaseModel):
    """세션 삭제 요청 스키마.

    Args:
        session_id: 삭제할 세션 식별자.

    Returns:
        SessionDiscardRequest: 유효성 검증이 완료된 요청 객체.
    """

    session_id: str


class SessionOpResponse(BaseModel):
    """세션 작업 응답 스키마.

    Args:
        ok: 작업 성공 여부.
        detail: 상세 설명.

    Returns:
        SessionOpResponse: 직렬화 가능한 응답 객체.
    """

    ok: bool
    detail: str
