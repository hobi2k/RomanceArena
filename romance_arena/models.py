from __future__ import annotations

"""도메인 공통 타입/데이터 모델 정의."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class RelationshipStage(str, Enum):
    """관계 단계를 나타내는 enum."""

    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    ROMANTIC_INTEREST = "romantic_interest"
    DATING = "dating"
    RELATIONSHIP = "relationship"


class Action(str, Enum):
    """턴에서 선택 가능한 행동 enum."""

    TALK = "talk"
    COMPLIMENT = "compliment"
    GIFT = "gift"
    INVITE_DATE = "invite_date"
    APOLOGIZE = "apologize"
    JOKE = "joke"
    TEASE = "tease"
    IGNORE = "ignore"
    CHANGE_TOPIC = "change_topic"


MoodLabel = Literal["angry", "sad", "neutral", "shy", "happy", "jealous"]


@dataclass
class RelationshipState:
    """관계 상태 수치 집합.

    모든 수치는 1~100 범위를 사용하며, `clamp()`로 범위를 강제한다.
    """

    affection: int = 35
    trust: int = 30
    interest: int = 35
    jealousy: int = 15
    mood: int = 50
    relationship_stage: RelationshipStage = RelationshipStage.ACQUAINTANCE

    def clamp(self) -> None:
        """모든 상태 수치를 [1, 100] 범위로 보정한다."""
        self.affection = max(1, min(100, self.affection))
        self.trust = max(1, min(100, self.trust))
        self.interest = max(1, min(100, self.interest))
        self.jealousy = max(1, min(100, self.jealousy))
        self.mood = max(1, min(100, self.mood))

    @property
    def mood_label(self) -> MoodLabel:
        """현재 mood/jealousy 수치를 요약 라벨로 변환한다."""
        if self.jealousy >= 70:
            return "jealous"
        if self.mood <= 20:
            return "angry"
        if self.mood <= 40:
            return "sad"
        if self.mood <= 60:
            return "neutral"
        if self.mood <= 80:
            return "shy"
        return "happy"


@dataclass
class TurnResult:
    """엔진 1턴 실행 결과.

    API/CLI 응답의 원본 데이터 구조로 사용한다.
    """

    player_action: Action
    npc_action: Action
    reason: str
    player_turn_text: str
    npc_turn_text: str
    npc_dialogue: str
    state: RelationshipState
    outcome: str = "ongoing"
    events: list[str] = field(default_factory=list)
