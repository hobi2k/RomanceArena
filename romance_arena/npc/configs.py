from __future__ import annotations

from dataclasses import dataclass

from ..models import Action


@dataclass(frozen=True)
class NPCProfile:
    npc_id: str
    name: str
    personality: str
    persona: str
    scenario: str
    player_actions: tuple[Action, ...]
    npc_actions: tuple[Action, ...]


NPCS: dict[str, NPCProfile] = {
    "saya": NPCProfile(
        npc_id="saya",
        name="사야",
        personality="kind",
        persona="다정하고 공감 능력이 높은 성격. 감정적 안정과 신뢰를 중요시한다.",
        scenario="같은 동아리에서 자주 마주치는 라이벌 관계.",
        player_actions=(
            Action.TALK,
            Action.COMPLIMENT,
            Action.GIFT,
            Action.INVITE_DATE,
            Action.APOLOGIZE,
            Action.JOKE,
            Action.TEASE,
            Action.IGNORE,
        ),
        npc_actions=(
            Action.TALK,
            Action.COMPLIMENT,
            Action.TEASE,
            Action.APOLOGIZE,
            Action.IGNORE,
            Action.CHANGE_TOPIC,
            Action.INVITE_DATE,
        ),
    ),
    "mai": NPCProfile(
        npc_id="mai",
        name="마이",
        personality="tsundere",
        persona="장난기 있지만 속은 여린 츤데레. 관심 표현이 서툴고 간접적으로 드러낸다.",
        scenario="카페 아르바이트에서 단골로 만나 대화가 쌓이는 상황.",
        player_actions=(
            Action.TALK,
            Action.COMPLIMENT,
            Action.GIFT,
            Action.INVITE_DATE,
            Action.APOLOGIZE,
            Action.JOKE,
            Action.TEASE,
            Action.IGNORE,
        ),
        npc_actions=(
            Action.TALK,
            Action.COMPLIMENT,
            Action.TEASE,
            Action.APOLOGIZE,
            Action.IGNORE,
            Action.CHANGE_TOPIC,
            Action.INVITE_DATE,
        ),
    ),
}
