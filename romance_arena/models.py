from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class RelationshipStage(str, Enum):
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    ROMANTIC_INTEREST = "romantic_interest"
    DATING = "dating"
    RELATIONSHIP = "relationship"


class Action(str, Enum):
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
    affection: int = 35
    trust: int = 30
    interest: int = 35
    jealousy: int = 15
    mood: int = 50
    relationship_stage: RelationshipStage = RelationshipStage.ACQUAINTANCE

    def clamp(self) -> None:
        self.affection = max(1, min(100, self.affection))
        self.trust = max(1, min(100, self.trust))
        self.interest = max(1, min(100, self.interest))
        self.jealousy = max(1, min(100, self.jealousy))
        self.mood = max(1, min(100, self.mood))

    @property
    def mood_label(self) -> MoodLabel:
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
    player_action: Action
    npc_action: Action
    reason: str
    player_turn_text: str
    npc_turn_text: str
    npc_dialogue: str
    state: RelationshipState
    outcome: str = "ongoing"
    events: list[str] = field(default_factory=list)
