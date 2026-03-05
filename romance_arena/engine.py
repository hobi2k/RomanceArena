from __future__ import annotations

from dataclasses import dataclass, field

from .environment import RomanceEnvironment
from .memory_store import SQLiteMemoryStore
from .models import Action, TurnResult
from .npc.agent import RomanceNPCAgent
from .npc.configs import NPCProfile
from .player.generator import PlayerTurnGenerator
from .player.renderer import render_player_turn_fallback


@dataclass
class Session:
    session_id: str
    npc_id: str
    turn: int = 0
    logs: list[dict] = field(default_factory=list)


class RomanceArenaEngine:
    def __init__(self, profile: NPCProfile, session_id: str, memory: SQLiteMemoryStore | None = None) -> None:
        self.profile = profile
        self.env = RomanceEnvironment()
        self.agent = RomanceNPCAgent(profile)
        self.player_turn_generator = PlayerTurnGenerator()
        self.memory = memory or SQLiteMemoryStore()
        self.session = Session(session_id=session_id, npc_id=profile.npc_id)
        # 세션 시작 시점의 장기기억 시드.
        self.memory.upsert_long_term(
            session_id=session_id,
            memory_key="first_meeting",
            note=f"{profile.name}와 첫 만남",
            turn=0,
            score=2,
        )

    def step(self, player_action: Action) -> TurnResult:
        # 1) player action 적용
        # 2) 메모리 조회 + npc action 결정
        # 3) npc action 적용
        # 4) 결과/메모리 저장
        self.session.turn += 1
        events = []
        transition_notes: list[str] = []
        pre_recent_events = self.env.events[-8:]
        pre_long_term = self.memory.list_long_term(self.session.session_id)[:6]
        player_turn_text = self.player_turn_generator.generate_turn_text(
            profile=self.profile,
            state=self.env.state,
            player_action=player_action,
            recent_events=pre_recent_events,
            long_term_memory=pre_long_term,
        ) or render_player_turn_fallback(player_action)

        # player action의 상태 변화량도 우선 LLM이 결정한다(실패 시 룰 기반 fallback).
        player_delta_decision = self.agent.decide_state_delta(
            state=self.env.state,
            actor="player",
            action=player_action,
            player_action=player_action,
            recent_events=pre_recent_events,
            long_term_memory=pre_long_term,
        )
        if player_delta_decision is not None:
            transition_notes.append(f"player_delta={player_delta_decision.reason}")
        events.extend(
            self.env.apply_action(
                player_action,
                actor="player",
                llm_deltas=player_delta_decision.deltas if player_delta_decision else None,
            )
        )
        recent_events = self.memory.get_recent_events(self.session.session_id, limit=6) + self.env.events[-6:]
        # sqlite-vec 사용 가능 시 의미 기반 retrieval, 아니면 lexical fallback.
        query_text = f"player_action={player_action.value}; recent_events={recent_events[-4:]}"
        long_term = self.memory.retrieve_long_term(
            self.session.session_id,
            query_text=query_text,
            limit=6,
        )
        decision = self.agent.choose_action(
            state=self.env.state,
            player_action=player_action,
            recent_events=recent_events,
            long_term_memory=long_term,
        )
        npc_delta_decision = self.agent.decide_state_delta(
            state=self.env.state,
            actor="npc",
            action=decision.action,
            player_action=player_action,
            recent_events=recent_events,
            long_term_memory=long_term,
        )
        if npc_delta_decision is not None:
            transition_notes.append(f"npc_delta={npc_delta_decision.reason}")
        events.extend(
            self.env.apply_action(
                decision.action,
                actor="npc",
                llm_deltas=npc_delta_decision.deltas if npc_delta_decision else None,
            )
        )

        outcome = self.env.evaluate_outcome()
        npc_turn_text = decision.dialogue
        result = TurnResult(
            player_action=player_action,
            npc_action=decision.action,
            reason=" | ".join([decision.reason] + transition_notes),
            player_turn_text=player_turn_text,
            npc_turn_text=npc_turn_text,
            npc_dialogue=decision.dialogue,
            state=self.env.state,
            outcome=outcome,
            events=events,
        )

        state_snapshot = self.env.snapshot()
        self.memory.save_turn(
            session_id=self.session.session_id,
            turn=self.session.turn,
            player_action=player_action.value,
            npc_action=decision.action.value,
            events=events,
            state=state_snapshot,
        )
        self._promote_long_term_memories_llm(
            player_action=player_action,
            npc_action=decision.action,
            events=events,
        )

        self.session.logs.append(
            {
                "turn": self.session.turn,
                "player_action": player_action.value,
                "npc_action": decision.action.value,
                "state": state_snapshot,
                "events": events,
                "outcome": outcome,
            }
        )
        return result

    def _promote_long_term_memories_llm(
        self,
        *,
        player_action: Action,
        npc_action: Action,
        events: list[str],
    ) -> None:
        sid = self.session.session_id
        turn = self.session.turn
        decision = self.agent.extract_long_term_memories(
            turn=turn,
            state=self.env.state,
            player_action=player_action,
            npc_action=npc_action,
            events=events,
            recent_events=self.env.events[-12:],
            recent_long_term=self.memory.list_long_term(sid),
        )
        if decision is None:
            return
        for item in decision.memories:
            self.memory.upsert_long_term(
                session_id=sid,
                memory_key=str(item["memory_key"]),
                note=str(item["note"]),
                turn=turn,
                score=int(item["score"]),
            )
