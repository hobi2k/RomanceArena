from __future__ import annotations

"""플레이어 턴 텍스트 생성 계층.

역할:
1. LLM을 사용해 플레이어 턴 텍스트(서술 + 대사)를 생성
2. 모델 출력 형식을 프로젝트 표준으로 정규화

출력 표준 형식:
- 1행: 3인칭 서술 문장
- 2행: 큰따옴표로 감싼 대사 문장
"""

from ..models import Action, RelationshipState
from ..npc.configs import NPCProfile
from ..npc.llm_client import OpenAICompatFunctionCaller


class PlayerTurnGenerator:
    """LLM 기반 플레이어 턴 텍스트 생성기."""

    def __init__(self) -> None:
        # NPC 계층과 동일한 OpenAI 호환 클라이언트를 재사용한다.
        self.llm = OpenAICompatFunctionCaller()

    def generate_turn_text(
        self,
        *,
        profile: NPCProfile,
        state: RelationshipState,
        player_action: Action,
        recent_events: list[str],
        long_term_memory: list[dict],
    ) -> str | None:
        """플레이어 턴 텍스트를 생성한다.

        Returns:
            - str: 정규화된 `서술\\n"대사"` 형식 텍스트
            - None: LLM 비활성(mock) 또는 호출 실패
        """
        if not self.llm.enabled():
            return None
        system_prompt = """
                        너는 연애 시뮬레이션에서 플레이어 턴 텍스트를 생성한다.
                        출력은 서술 1블록 + 대사 1블록으로 작성한다.
                        서술은 3인칭 평어체로 작성하고, 대사는 큰따옴표로 감싼다.
                        """
        user_prompt = f"""
                        npc_name={profile.name}
                        npc_personality={profile.personality}
                        npc_persona={profile.persona}
                        scenario={profile.scenario}
                        state={{affection:{state.affection}, trust:{state.trust}, interest:{state.interest}, jealousy:{state.jealousy}, mood:{state.mood}, stage:{state.relationship_stage.value}}}
                        player_action={player_action.value}
                        recent_events={recent_events[-8:]}
                        long_term_memory={long_term_memory[:6]}
                        플레이어 시점으로 출력
                        """
        try:
            text = self.llm.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.75,
                max_tokens=120,
            )
        except Exception:
            return None
        # 모델 편차를 줄이기 위해 반드시 표준 형식으로 정규화한다.
        return normalize_scene_dialogue(text)


def normalize_scene_dialogue(text: str) -> str:
    """서술+대사 텍스트를 표준 형식으로 정규화한다.

    허용 입력:
    - 이미 표준 형식인 2줄 텍스트
    - `서술:`, `대사:` 라벨 형태
    - 1줄만 있는 출력(이 경우 기본 서술을 보강)

    반환은 항상:
        `<서술 문장>\\n"<대사 문장>"`
    """
    # 일부 모델은 "\\n" 문자열을 그대로 출력하므로 실제 줄바꿈으로 복원한다.
    t = text.strip().replace("\\n", "\n")
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    narration = ""
    dialogue = ""
    # 라벨형 출력(`서술:`, `대사:`)이 들어온 경우 라벨 제거 후 재구성한다.
    if "서술:" in t or "대사:" in t:
        narration = next((ln.replace("서술:", "", 1).strip() for ln in lines if ln.startswith("서술:")), "")
        dialogue = next((ln.replace("대사:", "", 1).strip() for ln in lines if ln.startswith("대사:")), "")
    elif len(lines) >= 2:
        # 이미 2줄이면 1행=서술, 2행=대사로 간주한다.
        narration, dialogue = lines[0], lines[1]
    elif len(lines) == 1:
        # 1줄만 있을 때는 기본 서술을 보강해 형식을 맞춘다.
        narration, dialogue = "플레이어는 잠시 생각을 정리하며 숨을 고른다.", lines[0]

    # 최종 안전장치: 둘 중 하나라도 비면 기본 문구로 채운다.
    if not narration:
        narration = "플레이어는 잠시 생각을 정리하며 숨을 고른다."
    if not dialogue:
        dialogue = "..."
    # 대사는 반드시 큰따옴표 한 겹으로 강제한다.
    dialogue = dialogue.strip().strip('"').strip()
    return f"{narration}\n\"{dialogue}\""
