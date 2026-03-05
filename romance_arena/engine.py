from __future__ import annotations

"""게임 오케스트레이션 엔진.

엔진은 하위 컴포넌트(npc/player/environment/memory)를 조합해
한 턴의 전체 흐름을 실행한다.
"""

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
    """세션 런타임 메타데이터."""

    session_id: str
    npc_id: str
    turn: int = 0
    logs: list[dict] = field(default_factory=list)


class RomanceArenaEngine:
    """Romance Arena 턴 실행기."""

    def __init__(self, profile: NPCProfile, session_id: str, memory: SQLiteMemoryStore | None = None) -> None:
        self.profile = profile
        self.env = RomanceEnvironment()
        self.agent = RomanceNPCAgent(profile)
        self.player_turn_generator = PlayerTurnGenerator()
        # 외부에서 memory store 주입 가능(테스트/교체 용이성).
        self.memory = memory or SQLiteMemoryStore()
        self.session = Session(session_id=session_id, npc_id=profile.npc_id)
        # 세션 시작 시점 장기기억 시드.
        self.memory.upsert_long_term(
            session_id=session_id,
            memory_key="first_meeting",
            note=f"{profile.name}와 첫 만남",
            turn=0,
            score=2,
        )

    def step(self, player_action: Action) -> TurnResult:
        """한 턴을 실행하고 결과를 반환한다.

        실행 순서:
        1. 플레이어 턴 텍스트 생성
        2. 플레이어 상태 변화 적용
        3. 장기기억 retrieval 후 NPC 행동 결정
        4. NPC 상태 변화 적용
        5. 결과 판정 + 메모리 저장 + 장기기억 승격
        """
        self.session.turn += 1
        events = []
        transition_notes: list[str] = []

        # 전이 전 문맥(최근 이벤트/장기기억)을 캐시해서
        # 플레이어 텍스트 생성 및 delta 추론에 동일 입력을 사용한다.
        pre_recent_events = self.env.events[-8:]
        pre_long_term = self.memory.list_long_term(self.session.session_id)[:6]

        # 플레이어 턴 텍스트는 LLM 우선, 실패 시 템플릿 fallback.
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

        # 방금 반영된 이벤트를 포함해 NPC 의사결정 입력 문맥을 구성한다.
        recent_events = self.memory.get_recent_events(self.session.session_id, limit=6) + self.env.events[-6:]
        # sqlite-vec 가능 시 의미 검색, 실패 시 lexical fallback.
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

        # outcome은 환경 계층의 중앙 규칙으로 판정한다.
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
        # short-term 메모리(턴 로그) 저장.
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

        # 디버깅/리플레이용 로그.
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
        """LLM 기반 장기기억 승격.

        NPC 에이전트가 추출한 `memory_key/note/score` 후보를
        메모리 저장소에 upsert한다.
        """
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
        # 동일 memory_key는 저장소에서 누적/병합(upsert)된다.
        for item in decision.memories:
            self.memory.upsert_long_term(
                session_id=sid,
                memory_key=str(item["memory_key"]),
                note=str(item["note"]),
                turn=turn,
                score=int(item["score"]),
            )
