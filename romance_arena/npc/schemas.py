from __future__ import annotations

from typing import Any

from ..models import Action


NPC_TOOL_SCHEMA: dict[str, Any] = {
    "name": "choose_npc_action",
    "description": "현재 턴에서 NPC가 수행할 단일 행동을 선택한다.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [a.value for a in Action],
                "description": "선택된 NPC 행동.",
            },
            "reason": {
                "type": "string",
                "description": "행동 선택 근거를 한 줄로 작성.",
            },
            "dialogue": {
                "type": "string",
                "description": '서술 1블록 + 대사 1블록 형식. 예: \'사야는 잠시 숨을 골랐다.\\n"괜찮아요."\'',
            },
        },
        "required": ["action", "reason", "dialogue"],
        "additionalProperties": False,
    },
}


def validate_tool_payload(payload: dict[str, Any]) -> tuple[Action, str, str]:
    action_raw = payload.get("action")
    reason = payload.get("reason")
    dialogue = payload.get("dialogue")

    if not isinstance(action_raw, str):
        raise ValueError("action must be a string")
    try:
        action = Action(action_raw)
    except ValueError as exc:
        raise ValueError(f"invalid action: {action_raw}") from exc

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be non-empty string")
    if not isinstance(dialogue, str) or not dialogue.strip():
        raise ValueError("dialogue must be non-empty string")

    return action, reason.strip(), dialogue.strip()


STATE_DELTA_TOOL_SCHEMA: dict[str, Any] = {
    "name": "choose_state_delta",
    "description": (
        "행위자/행동/상황을 바탕으로 상태 변화량(delta)을 결정한다. "
        "반환값은 범위 제한된 정수 delta만 허용한다."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "delta_affection": {"type": "integer", "minimum": -10, "maximum": 10},
            "delta_trust": {"type": "integer", "minimum": -10, "maximum": 10},
            "delta_interest": {"type": "integer", "minimum": -10, "maximum": 10},
            "delta_jealousy": {"type": "integer", "minimum": -10, "maximum": 10},
            "delta_mood": {"type": "integer", "minimum": -10, "maximum": 10},
            "reason": {"type": "string"},
        },
        "required": [
            "delta_affection",
            "delta_trust",
            "delta_interest",
            "delta_jealousy",
            "delta_mood",
            "reason",
        ],
        "additionalProperties": False,
    },
}


def validate_state_delta_payload(payload: dict[str, Any]) -> tuple[dict[str, int], str]:
    keys = [
        "delta_affection",
        "delta_trust",
        "delta_interest",
        "delta_jealousy",
        "delta_mood",
    ]
    out: dict[str, int] = {}
    for key in keys:
        val = payload.get(key)
        if not isinstance(val, int) or not (-10 <= val <= 10):
            raise ValueError(f"{key} must be integer in [-10, 10]")
        out[key] = val

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be non-empty string")
    return out, reason.strip()


LONG_TERM_MEMORY_TOOL_SCHEMA: dict[str, Any] = {
    "name": "extract_long_term_memory",
    "description": "현재 턴 로그를 보고 장기 기억으로 승격할 항목을 추출한다.",
    "parameters": {
        "type": "object",
        "properties": {
            "memories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "memory_key": {
                            "type": "string",
                            "description": "기억 항목 식별 키(중복 시 동일 키 사용).",
                        },
                        "note": {
                            "type": "string",
                            "description": "장기 기억에 저장할 요약 노트.",
                        },
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "중요도 가중치(1~5).",
                        },
                    },
                    "required": ["memory_key", "note", "score"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["memories"],
        "additionalProperties": False,
    },
}


def validate_long_term_memory_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("memories")
    if not isinstance(raw, list):
        raise ValueError("memories must be a list")

    out: list[dict[str, Any]] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        key = item.get("memory_key")
        note = item.get("note")
        score = item.get("score")
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(note, str) or not note.strip():
            continue
        if not isinstance(score, int) or not (1 <= score <= 5):
            continue
        norm_key = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in key.strip().lower())
        norm_key = "_".join(part for part in norm_key.split("_") if part)
        if not norm_key:
            continue
        out.append({"memory_key": norm_key, "note": note.strip(), "score": score})
    return out
