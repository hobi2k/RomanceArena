from __future__ import annotations

from ..models import Action, RelationshipState
from ..npc.configs import NPCProfile
from ..npc.llm_client import OpenAICompatFunctionCaller


class PlayerTurnGenerator:
    def __init__(self) -> None:
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
        return normalize_scene_dialogue(text)


def normalize_scene_dialogue(text: str) -> str:
    t = text.strip().replace("\\n", "\n")
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    narration = ""
    dialogue = ""
    if "서술:" in t or "대사:" in t:
        narration = next((ln.replace("서술:", "", 1).strip() for ln in lines if ln.startswith("서술:")), "")
        dialogue = next((ln.replace("대사:", "", 1).strip() for ln in lines if ln.startswith("대사:")), "")
    elif len(lines) >= 2:
        narration, dialogue = lines[0], lines[1]
    elif len(lines) == 1:
        narration, dialogue = "플레이어는 잠시 생각을 정리하며 숨을 고른다.", lines[0]

    if not narration:
        narration = "플레이어는 잠시 생각을 정리하며 숨을 고른다."
    if not dialogue:
        dialogue = "..."
    dialogue = dialogue.strip().strip('"').strip()
    return f"{narration}\n\"{dialogue}\""
