from __future__ import annotations

import random
from dataclasses import dataclass

from ..models import Action, RelationshipStage, RelationshipState
from .configs import NPCProfile
from .llm_client import OpenAICompatFunctionCaller
from ..player.generator import normalize_scene_dialogue
from .schemas import (
    LONG_TERM_MEMORY_TOOL_SCHEMA,
    NPC_TOOL_SCHEMA,
    STATE_DELTA_TOOL_SCHEMA,
    validate_long_term_memory_payload,
    validate_state_delta_payload,
    validate_tool_payload,
)


@dataclass
class AgentDecision:
    action: Action
    reason: str
    dialogue: str


@dataclass
class StateDeltaDecision:
    deltas: dict[str, int]
    reason: str


@dataclass
class LongTermMemoryDecision:
    memories: list[dict[str, str | int]]


PERSONALITY_WEIGHTS: dict[str, dict[Action, float]] = {
    "tsundere": {
        Action.TEASE: 1.5,
        Action.TALK: 1.2,
        Action.COMPLIMENT: 0.8,
        Action.APOLOGIZE: 1.0,
        Action.IGNORE: 0.9,
        Action.CHANGE_TOPIC: 1.1,
        Action.INVITE_DATE: 1.0,
    },
    "kind": {
        Action.TALK: 1.3,
        Action.COMPLIMENT: 1.3,
        Action.APOLOGIZE: 1.2,
        Action.TEASE: 0.8,
        Action.IGNORE: 0.6,
        Action.CHANGE_TOPIC: 1.0,
        Action.INVITE_DATE: 1.0,
    },
}


class RomanceNPCAgent:
    def __init__(self, profile: NPCProfile, seed: int = 42) -> None:
        self.profile = profile
        self.random = random.Random(seed)
        self.llm = OpenAICompatFunctionCaller()

    def choose_action(
        self,
        *,
        state: RelationshipState,
        player_action: Action,
        recent_events: list[str],
        long_term_memory: list[dict],
    ) -> AgentDecision:
        policy_weights = self._build_policy_weights(state, player_action, recent_events)
        if self.llm.enabled():
            decision = self._try_llm_function_call(
                state=state,
                player_action=player_action,
                recent_events=recent_events,
                long_term_memory=long_term_memory,
                policy_weights=policy_weights,
            )
            if decision is not None:
                return decision
        return self._policy_fallback(state, player_action, policy_weights)

    def decide_state_delta(
        self,
        *,
        state: RelationshipState,
        actor: str,
        action: Action,
        player_action: Action,
        recent_events: list[str],
        long_term_memory: list[dict],
    ) -> StateDeltaDecision | None:
        if not self.llm.enabled():
            return None
        system_prompt = """너는 Romance Arena 상태전이 추론기다.
                        반드시 function call로만 응답하라.
                        delta_* 값은 모두 -10~10 정수 범위만 허용된다."""
        user_prompt = f"""npc_name={self.profile.name}
                        personality={self.profile.personality}
                        persona={self.profile.persona}
                        scenario={self.profile.scenario}
                        state={{affection:{state.affection}, trust:{state.trust}, interest:{state.interest}, jealousy:{state.jealousy}, mood:{state.mood}, stage:{state.relationship_stage.value}}}
                        actor={actor}
                        action={action.value}
                        player_action={player_action.value}
                        recent_events={recent_events[-8:]}
                        long_term_memory={long_term_memory[:6]}
                        출력은 상태 변화량(delta)만 포함"""
        try:
            payload = self.llm.choose_action_payload(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tool_schema=STATE_DELTA_TOOL_SCHEMA,
            )
            deltas, reason = validate_state_delta_payload(payload)
        except Exception:
            return None
        return StateDeltaDecision(deltas=deltas, reason=reason)

    def extract_long_term_memories(
        self,
        *,
        turn: int,
        state: RelationshipState,
        player_action: Action,
        npc_action: Action,
        events: list[str],
        recent_events: list[str],
        recent_long_term: list[dict],
    ) -> LongTermMemoryDecision | None:
        if not self.llm.enabled():
            return None
        system_prompt = """
                        너는 장기 기억 승격 판단기다.
                        현재 턴 정보를 보고 장기 기억으로 남길 핵심 사건만 추출한다.
                        반드시 function call로만 응답하라.
                        기억은 최대 3개로 제한하고, memory_key는 소문자 snake_case 또는 kebab-case로 작성한다.
                        """
        user_prompt = f"""
                        turn={turn}
                        npc_name={self.profile.name}
                        personality={self.profile.personality}
                        state={{affection:{state.affection}, trust:{state.trust}, interest:{state.interest}, jealousy:{state.jealousy}, mood:{state.mood}, stage:{state.relationship_stage.value}}}
                        player_action={player_action.value}
                        npc_action={npc_action.value}
                        events={events}
                        recent_events={recent_events[-10:]}
                        recent_long_term={recent_long_term[:8]}
                        중복 기억은 같은 memory_key를 재사용하고, 신규 핵심 사건만 추출
                        """
        try:
            payload = self.llm.choose_action_payload(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tool_schema=LONG_TERM_MEMORY_TOOL_SCHEMA,
            )
            memories = validate_long_term_memory_payload(payload)
        except Exception:
            return None
        if not memories:
            return LongTermMemoryDecision(memories=[])
        return LongTermMemoryDecision(memories=memories[:3])

    def _try_llm_function_call(
        self,
        *,
        state: RelationshipState,
        player_action: Action,
        recent_events: list[str],
        long_term_memory: list[dict],
        policy_weights: dict[Action, float],
    ) -> AgentDecision | None:
        system_prompt = '''너는 Romance Arena NPC 의사결정 에이전트다.
                        반드시 function call로만 응답하라.
                        action은 allowed_actions 안에서만 선택한다.
                        dialogue는 아래 형식을 반드시 지킨다.
                        출력은 서술 1블록 + 대사 1블록으로 작성한다.
                        서술은 3인칭 평어체로 작성하고, 대사는 큰따옴표로 감싼다.'''
        user_prompt = f"""npc_name={self.profile.name}
                        personality={self.profile.personality}
                        persona={self.profile.persona}
                        scenario={self.profile.scenario}
                        state={{affection:{state.affection}, trust:{state.trust}, interest:{state.interest}, jealousy:{state.jealousy}, mood:{state.mood}, stage:{state.relationship_stage.value}}}
                        player_action={player_action.value}
                        recent_events={recent_events[-8:]}
                        long_term_memory={long_term_memory[:6]}
                        allowed_actions={[a.value for a in self.profile.npc_actions]}"""

        try:
            payload = self.llm.choose_action_payload(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tool_schema=NPC_TOOL_SCHEMA,
            )
            action, reason, dialogue = validate_tool_payload(payload)
        except Exception:
            return None

        if action not in self.profile.npc_actions:
            return None
        adjusted_action = self._blend_llm_with_policy(action, policy_weights)
        if adjusted_action != action:
            reason = f"{reason} | adjusted_by_personality_policy={adjusted_action.value}"

        if len(dialogue.strip()) < 8:
            regenerated = self._generate_dialogue_with_llm(
                state=state,
                player_action=player_action,
                npc_action=adjusted_action,
            )
            if regenerated:
                dialogue = regenerated
        dialogue = normalize_scene_dialogue(dialogue)
        return AgentDecision(action=adjusted_action, reason=reason, dialogue=dialogue)

    def _policy_fallback(
        self,
        state: RelationshipState,
        player_action: Action,
        policy_weights: dict[Action, float],
    ) -> AgentDecision:
        action = self._weighted_choice(policy_weights)
        reason = "성격 기반 가중치와 현재 상태를 반영한 fallback 정책(action only)."
        dialogue = self._generate_dialogue_with_llm(
            state=state,
            player_action=player_action,
            npc_action=action,
        ) or self._build_dialogue(action, state)
        dialogue = normalize_scene_dialogue(dialogue)
        return AgentDecision(action=action, reason=reason, dialogue=dialogue)

    def _build_policy_weights(
        self,
        state: RelationshipState,
        player_action: Action,
        recent_events: list[str],
    ) -> dict[Action, float]:
        weights = self._base_weights()
        self._apply_state_bias(weights, state, player_action, recent_events)
        return weights

    def _base_weights(self) -> dict[Action, float]:
        base = {a: 1.0 for a in self.profile.npc_actions}
        personality_map = PERSONALITY_WEIGHTS.get(self.profile.personality, {})
        for action in self.profile.npc_actions:
            base[action] *= personality_map.get(action, 1.0)
        return base

    def _apply_state_bias(
        self,
        weights: dict[Action, float],
        state: RelationshipState,
        player_action: Action,
        recent_events: list[str],
    ) -> None:
        if state.trust < 25 and Action.APOLOGIZE in weights:
            weights[Action.APOLOGIZE] *= 2.0
        if state.jealousy > 65:
            if Action.APOLOGIZE in weights:
                weights[Action.APOLOGIZE] *= 1.8
            if Action.CHANGE_TOPIC in weights:
                weights[Action.CHANGE_TOPIC] *= 1.4
        if player_action == Action.IGNORE and Action.IGNORE in weights:
            weights[Action.IGNORE] *= 1.5
        if player_action == Action.COMPLIMENT and Action.TEASE in weights:
            weights[Action.TEASE] *= 1.4
        if state.relationship_stage in {
            RelationshipStage.ROMANTIC_INTEREST,
            RelationshipStage.DATING,
            RelationshipStage.RELATIONSHIP,
        } and state.interest > 70 and Action.INVITE_DATE in weights:
            weights[Action.INVITE_DATE] *= 1.7
        if "first_argument" in recent_events[-3:] and Action.APOLOGIZE in weights:
            weights[Action.APOLOGIZE] *= 1.6

    def _blend_llm_with_policy(
        self,
        llm_action: Action,
        policy_weights: dict[Action, float],
    ) -> Action:
        max_weight = max(policy_weights.values())
        llm_weight = policy_weights.get(llm_action, 0.0)
        if llm_weight >= max_weight * 0.75:
            return llm_action
        best_actions = [a for a, w in policy_weights.items() if w == max_weight]
        return self.random.choice(best_actions)

    def _weighted_choice(self, weights: dict[Action, float]) -> Action:
        items = list(weights.items())
        total = sum(max(0.01, w) for _, w in items)
        r = self.random.random() * total
        c = 0.0
        for action, weight in items:
            c += max(0.01, weight)
            if r <= c:
                return action
        return items[-1][0]

    def _generate_dialogue_with_llm(
        self,
        *,
        state: RelationshipState,
        player_action: Action,
        npc_action: Action,
    ) -> str | None:
        if not self.llm.enabled():
            return None
        system_prompt = """너는 연애 시뮬레이션 NPC 턴 텍스트를 생성한다.
                        캐릭터 일관성을 유지한 자연스러운 한국어로 작성하라.
                        출력은 서술 1블록 + 대사 1블록으로 작성한다.
                        서술은 3인칭 평어체로 작성하고, 대사는 큰따옴표로 감싼다."""
        user_prompt = f"""npc_name={self.profile.name}
                        personality={self.profile.personality}
                        persona={self.profile.persona}
                        state={{affection:{state.affection}, trust:{state.trust}, interest:{state.interest}, jealousy:{state.jealousy}, mood:{state.mood}, stage:{state.relationship_stage.value}}}
                        player_action={player_action.value}
                        npc_action={npc_action.value}
                        출력은 서술 1블록 + 대사 1블록"""
        try:
            text = self.llm.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=90,
            )
        except Exception:
            return None
        text = text.strip().strip('"').strip()
        if not text:
            return None
        return normalize_scene_dialogue(text)

    def _build_dialogue(self, action: Action, state: RelationshipState) -> str:
        name = self.profile.name
        if action == Action.APOLOGIZE:
            return f"{name}는 미안한 기색으로 시선을 살짝 낮췄다.\n\"아까는 내가 예민했어. 미안해.\""
        if action == Action.COMPLIMENT:
            return f"{name}는 상대를 가만히 바라보며 옅게 미소 지었다.\n\"네가 생각보다 섬세하네.\""
        if action == Action.TEASE:
            return f"{name}는 장난스러운 눈빛으로 반걸음 다가섰다.\n\"그런 반응이면 더 놀리고 싶어지는데?\""
        if action == Action.INVITE_DATE:
            return f"{name}는 잠시 망설이다가 조심스럽게 제안했다.\n\"이번 주말, 같이 나갈래?\""
        if action == Action.IGNORE:
            return f"{name}는 표정을 굳힌 채 시선을 피했다.\n\"...지금은 좀 혼자 있고 싶어.\""
        if action == Action.JOKE:
            return f"{name}는 분위기를 풀어보려는 듯 어깨를 가볍게 으쓱였다.\n\"분위기 너무 무거운데, 농담 하나 할까?\""
        if action == Action.CHANGE_TOPIC:
            return f"{name}는 화제를 돌리려는 듯 짧게 숨을 골랐다.\n\"잠깐, 다른 이야기로 넘어가자.\""
        if state.mood_label in {"happy", "shy"}:
            return f"{name}는 얼굴이 살짝 붉어진 채 미소를 지었다.\n\"너랑 있으면 이상하게 마음이 편해.\""
        return f"{name}는 감정을 가라앉히며 천천히 말을 이었다.\n\"음, 그 얘기부터 차근차근 해보자.\""
