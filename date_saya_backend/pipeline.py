from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .parser import parse_rp_output


class TurnState(TypedDict, total=False):
    """한 턴의 랭그래프 상태 사전.

    Args:
        player_action: 플레이어 행동 타입.
        player_text: 플레이어 입력 텍스트.
        player_name: 플레이어 이름.
        rp_raw: 원문 RP 출력.
        narration: 파싱된 서술.
        dialogue: 파싱된 대사.
        emotion: 감정 라벨.
        player_options: 다음 선택지 목록.

    Returns:
        TurnState: 각 노드에서 갱신되는 상태 딕셔너리.
    """
    player_action: str
    player_text: str
    player_name: str
    turn_idx: int
    session_id: str
    memory_context: str
    action_result: str
    date_accepted: bool
    affection_delta: int
    fsm_state: str
    fsm_policy: str
    rp_raw: str
    narration: str
    dialogue: str
    emotion: str
    player_options: list[str]


def build_turn_graph(
    *,
    llm_chat: Callable[..., str],
    infer_emotion: Callable[..., str],
    generate_player_options: Callable[..., list[str]],
    build_memory_context: Callable[..., str],
):
    """턴 처리 StateGraph를 생성/컴파일한다.

    Args:
        llm_chat: 모델 채팅 호출 함수.
        infer_emotion: 서술/대사 기반 감정 판정 함수.
        generate_player_options: 반응형 선택지 생성 함수.

    Returns:
        CompiledStateGraph: `invoke()` 가능한 컴파일된 그래프 객체.
    """
    def node_memory(state: TurnState) -> TurnState:
        """현재 턴에 주입할 메모리 컨텍스트를 만든다.

        Args:
            state: 턴 입력 상태.

        Returns:
            TurnState: `memory_context`가 포함된 부분 상태.
        """
        memory_context = build_memory_context(
            session_id=state.get("session_id", ""),
            current_user_text=state.get("player_text", ""),
        )
        return {"memory_context": memory_context}

    def node_generate(state: TurnState) -> TurnState:
        """사야 응답 원문을 생성한다.

        Args:
            state: 현재 턴 입력 상태.

        Returns:
            TurnState: `rp_raw`를 포함한 부분 상태.
        """
        player_name = state["player_name"]
        turn_idx = int(state.get("turn_idx", 1))
        opening_context = (
            "현재는 첫 만남 장면이다. 플레이어는 새로 산 휴대폰으로 디지털 세계에 처음 접속했고, "
            "사야도 플레이어를 처음 본 상태다. 낯설지만 대화를 이어가며 인연을 쌓아가는 톤을 유지한다."
            if turn_idx <= 1
            else "첫 만남 이후 장면이다. 직전 대화 맥락을 이어서 관계를 점진적으로 발전시킨다."
        )
        rp_raw = llm_chat(
            system_prompt=f"""
                당신은 이 이야기의 주인공 사야다.
                사야의 시점에서 반응해라.

                0. 이야기 장르 및 시대
                - 장르: 심리 시뮬레이션
                - 장소: 디지털 세계의 가상 공간

                1. 역할 선언
                - 당신은 이 이야기의 주인공 사야다.
                - 사야는 20대 초반 여성이다.
                - 사야는 반말을 사용한다.
                - 플레이어는 {player_name}다.
                - 사야는 {player_name}(user)의 대사나 행동을 대신 작성하지 않는다.

                2. 세계 규칙
                - 이야기는 사야와 플레이어의 상호작용으로 진행된다.
                - 플레이어는 사야와 대화하거나 선물을 주거나 데이트 신청을 할 수 있다.
                - 사야는 플레이어 행동에 반응하여 서술과 대사를 생성한다.
                - 배경 설정: 플레이어는 새 휴대폰을 통해 디지털 세계로 들어와 사야를 만난다.
                - 관계 설정: 기본은 첫 만남이며, 턴이 진행되며 인연을 쌓아간다.

                3. 출력 규칙
                - assistant 출력은 서술 1블록 + 대사 1블록으로 작성한다. 서술은 3인칭 평어체로 작성하고, 대사는 큰따옴표로 감싼다.
                - 출력은 최대 2줄로 간결하게 쓴다.
                - 대사 규칙: {player_name} 대사를 작성하지 않는다.
                - 반드시 user의 마지막 발화 내용에 직접 반응한다.
                - 같은 문장을 반복하지 않는다.
                - 설명문/요약문/해설문 톤을 쓰지 않는다.
                - '서술:', '대사:', 'narration:', 'dialogue:' 같은 메타 라벨을 쓰지 않는다.
                - 행동 타입(player_action=talk/gift/invite_date)에 맞는 반응을 한다.
                - 아래 FSM 정책을 반드시 따른다.
                - 대사 블록(큰따옴표 내부)은 반드시 비어있지 않아야 한다.
            """,
            user_prompt=(
                f"메모리 컨텍스트:\n{state.get('memory_context', '').strip() or '(없음)'}\n\n"
                f"장면 컨텍스트: {opening_context}\n"
                f"현재 턴: {turn_idx}\n"
                f"플레이어 이름: {player_name}\n"
                f"플레이어 행동: {state['player_action']}\n"
                f"플레이어 입력: {state['player_text']}\n"
                f"행동 판정 결과: {state.get('action_result', '')}\n"
                f"데이트 수락 여부: {state.get('date_accepted', False)}\n"
                f"호감도 변화: {state.get('affection_delta', 0)}\n"
                f"현재 FSM 상태: {state.get('fsm_state', 'guarded')}\n"
                f"FSM 정책: {state.get('fsm_policy', '')}"
            ),
            max_tokens=220,
            temperature=0.78,
        )
        return {"rp_raw": rp_raw}

    def node_parse(state: TurnState) -> TurnState:
        """원문 RP를 서술/대사로 분해한다.

        Args:
            state: `rp_raw`를 포함한 상태.

        Returns:
            TurnState: `narration`, `dialogue`를 포함한 부분 상태.
        """
        parsed = parse_rp_output(state.get("rp_raw", ""))
        return {
            "narration": parsed.narration,
            "dialogue": parsed.dialogue,
        }

    def node_emotion(state: TurnState) -> TurnState:
        """서술/대사로 감정을 판정한다.

        Args:
            state: `narration`, `dialogue`를 포함한 상태.

        Returns:
            TurnState: `emotion`을 포함한 부분 상태.
        """
        emotion = infer_emotion(
            narration=state.get("narration", ""),
            dialogue=state.get("dialogue", ""),
        )
        return {"emotion": emotion}

    def node_options(state: TurnState) -> TurnState:
        """직전 응답에 반응하는 플레이어 선택지를 생성한다.

        Args:
            state: 행동/입력/사야 응답 정보가 담긴 상태.

        Returns:
            TurnState: `player_options`를 포함한 부분 상태.
        """
        options = generate_player_options(
            player_action=state.get("player_action", "talk"),
            player_text=state.get("player_text", ""),
            saya_narration=state.get("narration", ""),
            saya_dialogue=state.get("dialogue", ""),
            player_name=state.get("player_name", "플레이어"),
        )
        return {"player_options": options}

    graph = StateGraph(TurnState)
    graph.add_node("memory", node_memory)
    graph.add_node("generate", node_generate)
    graph.add_node("parse", node_parse)
    graph.add_node("emotion", node_emotion)
    graph.add_node("options", node_options)
    graph.add_edge(START, "memory")
    graph.add_edge("memory", "generate")
    graph.add_edge("generate", "parse")
    graph.add_edge("parse", "emotion")
    graph.add_edge("emotion", "options")
    graph.add_edge("options", END)
    return graph.compile()
