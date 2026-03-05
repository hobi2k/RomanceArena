from __future__ import annotations

"""NPC 설정 레지스트리.

이 모듈은 게임에서 선택 가능한 NPC의 정적 설정(성격/시나리오/허용 행동)을 관리한다.
엔진은 세션 시작 시 `NPCS`에서 프로필을 조회해 NPC 에이전트를 구성한다.
"""

from dataclasses import dataclass

from ..models import Action


@dataclass(frozen=True)
class NPCProfile:
    """NPC 1명의 고정 프로필."""

    npc_id: str
    name: str
    personality: str
    persona: str
    scenario: str
    player_actions: tuple[Action, ...]
    npc_actions: tuple[Action, ...]


# npc_id -> 프로필 매핑.
# 새 NPC를 추가할 때는 여기 엔트리를 추가하면 API/CLI 선택 목록에 자동 반영된다.
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
