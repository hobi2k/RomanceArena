from __future__ import annotations

from dataclasses import dataclass


SAYA_FSM_STATES = {"guarded", "warming_up", "open", "romantic"}


@dataclass(frozen=True)
class FsmTransitionInput:
    """FSM 상태 전이 입력값.

    Args:
        current_state: 이전 FSM 상태.
        player_action: 플레이어 행동.
        action_result: 액션 판정 결과.
        date_accepted: 데이트 수락 여부.
        affection_delta: 호감도 변화량.
        npc_emotion: 직전 NPC 감정.
        player_rel: 현재 관계 단계.

    Returns:
        FsmTransitionInput: 상태 전이 입력 데이터.
    """

    current_state: str
    player_action: str
    action_result: str
    date_accepted: bool
    affection_delta: int
    npc_emotion: str
    player_rel: str


def transition_saya_fsm(inp: FsmTransitionInput) -> str:
    """현재 턴 이벤트를 기반으로 다음 FSM 상태를 계산한다.

    Args:
        inp: 상태 전이 입력값.

    Returns:
        str: 다음 FSM 상태.
    """
    state = inp.current_state if inp.current_state in SAYA_FSM_STATES else "guarded"
    emo = (inp.npc_emotion or "neutral").lower().strip()
    rel = (inp.player_rel or "").strip()

    if inp.player_action == "invite_date":
        if inp.date_accepted:
            return "romantic"
        if inp.action_result.startswith("date_reject"):
            return "guarded"

    if inp.affection_delta >= 7:
        if state == "guarded":
            state = "warming_up"
        elif state == "warming_up":
            state = "open"
        elif state == "open" and rel in {"Lover", "Soulmate"}:
            state = "romantic"
    elif inp.affection_delta <= -3:
        if state == "romantic":
            state = "open"
        elif state == "open":
            state = "warming_up"
        else:
            state = "guarded"

    if emo in {"angry", "sad"} and inp.player_action in {"gift", "invite_date"}:
        if state == "romantic":
            state = "open"
        elif state == "open":
            state = "warming_up"
        else:
            state = "guarded"

    return state


def post_adjust_saya_fsm(*, base_state: str, current_emotion: str) -> str:
    """턴 종료 감정을 반영해 FSM 상태를 후조정한다.

    Args:
        base_state: 1차 계산 FSM 상태.
        current_emotion: 턴 종료 후 감정 라벨.

    Returns:
        str: 후조정 FSM 상태.
    """
    state = base_state if base_state in SAYA_FSM_STATES else "guarded"
    emo = (current_emotion or "neutral").strip().lower()
    if emo == "angry":
        if state == "romantic":
            return "open"
        if state == "open":
            return "warming_up"
        return "guarded"
    if emo == "sad" and state == "romantic":
        return "open"
    return state


def saya_fsm_policy_text(fsm_state: str) -> str:
    """FSM 상태별 사야 출력 정책 텍스트를 반환한다.

    Args:
        fsm_state: 사야 FSM 상태.

    Returns:
        str: 프롬프트 주입용 정책 텍스트.
    """
    state = fsm_state if fsm_state in SAYA_FSM_STATES else "guarded"
    policy_map = {
        "guarded": "거리감 유지. 짧고 조심스러운 반응. 데이트/선물에는 신중하게 경계 반응.",
        "warming_up": "호의가 보이지만 아직 확신 없음. 질문/탐색형 반응을 우선.",
        "open": "상대를 신뢰하며 감정 표현 증가. 대화 확장과 호감 표현 허용.",
        "romantic": "친밀하고 적극적. 데이트/관계 진전 제안에 긍정적 반응 가능.",
    }
    return policy_map[state]

