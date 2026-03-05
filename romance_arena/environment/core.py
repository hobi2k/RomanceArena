from __future__ import annotations

"""Environment 계층의 상태 전이 엔진.

이 모듈은 "행동(action) -> 상태(state) 갱신 -> 이벤트(event) 기록 -> 결과(outcome) 판정"
순서를 담당한다.

설계 원칙:
1. 상태 값은 항상 안전 범위(1~100)로 클램프한다.
2. 관계 단계(relationship_stage)는 매 턴 상태값으로부터 재계산한다.
3. 장기기억/로그 시스템에서 재사용할 이벤트 태그를 표준화한다.
4. LLM 기반 delta가 있으면 우선 사용하고, 없으면 규칙 기반 fallback을 사용한다.
"""

from dataclasses import asdict
from typing import Any

from ..models import Action, RelationshipStage, RelationshipState


def _stage_from_state(state: RelationshipState) -> RelationshipStage:
    """현재 수치 상태를 관계 단계(enum)로 변환한다.

    단계는 높은 친밀도 조건부터 우선 평가한다.
    즉, 상위 조건을 먼저 통과하면 더 낮은 단계는 검사하지 않는다.
    """
    if state.affection >= 90 and state.trust >= 80 and state.interest >= 85:
        return RelationshipStage.RELATIONSHIP
    if state.affection >= 78 and state.trust >= 65 and state.interest >= 72:
        return RelationshipStage.DATING
    if state.affection >= 65 and state.trust >= 55 and state.interest >= 60:
        return RelationshipStage.ROMANTIC_INTEREST
    if state.affection >= 50 and state.trust >= 40:
        return RelationshipStage.FRIEND
    if state.affection >= 30 and state.trust >= 25:
        return RelationshipStage.ACQUAINTANCE
    return RelationshipStage.STRANGER


class RomanceEnvironment:
    """Romance Arena의 상태 전이 컨테이너.

    Attributes:
        state: 현재 관계 상태(호감/신뢰/관심/질투/기분/단계).
        events: 턴 진행 중 누적되는 이벤트 태그 로그.
            - 세션 시작 시 `first_meeting` 시드 이벤트를 포함한다.
    """

    def __init__(self) -> None:
        self.state = RelationshipState()
        self.events: list[str] = ["first_meeting"]

    def snapshot(self) -> dict:
        """현재 상태를 직렬화 가능한 dict로 반환한다.

        메모리 저장/응답 전송용으로 사용되며, 계산형 속성(`mood_label`)도 포함한다.
        """
        data = asdict(self.state)
        data["mood_label"] = self.state.mood_label
        return data

    def apply_action(
        self,
        action: Action,
        actor: str,
        llm_deltas: dict[str, int] | None = None,
    ) -> list[str]:
        """행동 1회를 상태에 반영하고 발생 이벤트를 반환한다.

        Args:
            action: 이번 턴에 적용할 행동.
            actor: 행동 주체. `"player"` 또는 `"npc"`.
            llm_deltas: LLM이 제안한 상태 변화량.
                - 키: `delta_affection`, `delta_trust`, `delta_interest`,
                      `delta_jealousy`, `delta_mood`
                - 값 범위: -10 ~ 10 (본 함수에서 재검증/클램프)

        Returns:
            이번 적용으로 생성된 이벤트 태그 목록.
        """
        event_log: list[str] = []
        s = self.state

        if llm_deltas is not None:
            # 우선 경로: LLM이 제안한 delta를 적용한다.
            # 안전을 위해 타입/범위를 다시 보정한 후 반영한다.
            delta = self._sanitize_deltas(llm_deltas)
            s.affection += delta["delta_affection"]
            s.trust += delta["delta_trust"]
            s.interest += delta["delta_interest"]
            s.jealousy += delta["delta_jealousy"]
            s.mood += delta["delta_mood"]
            # 메모리 시스템과 호환되도록 이벤트 태그는 규칙으로 부여한다.
            self._tag_events_from_action(event_log, action=action, state=s)
        else:
            # fallback 경로: LLM delta가 없을 때만 규칙 기반 전이를 사용한다.
            if action == Action.TALK:
                s.affection += 3
                s.trust += 2
                s.mood += 3
            elif action == Action.COMPLIMENT:
                s.affection += 5
                s.interest += 3
                s.mood += 3
            elif action == Action.GIFT:
                s.affection += 5
                s.trust += 3
                s.interest += 3
                event_log.append("gift_received")
            elif action == Action.INVITE_DATE:
                if s.relationship_stage in {
                    RelationshipStage.FRIEND,
                    RelationshipStage.ROMANTIC_INTEREST,
                    RelationshipStage.DATING,
                    RelationshipStage.RELATIONSHIP,
                }:
                    s.affection += 6
                    s.interest += 6
                    s.trust += 3
                    event_log.append("date_invitation_positive")
                else:
                    s.trust -= 3
                    s.mood -= 3
                    event_log.append("date_invitation_too_early")
            elif action == Action.APOLOGIZE:
                s.trust += 5
                s.jealousy -= 3
                s.mood += 3
                event_log.append("apology_made")
            elif action == Action.JOKE:
                s.mood += 5
                s.affection += 3
            elif action == Action.TEASE:
                if s.trust >= 45:
                    s.affection += 3
                    s.interest += 3
                    s.mood += 2
                else:
                    s.trust -= 3
                    s.mood -= 3
                    s.jealousy += 2
                    event_log.append("first_argument")
            elif action == Action.CHANGE_TOPIC:
                s.mood += 2
                s.trust += 2
            elif action == Action.IGNORE:
                s.affection -= 5
                s.trust -= 5
                s.interest -= 3
                s.jealousy += 5
                s.mood -= 3
                event_log.append("ignored")
                event_log.append("first_argument")

        # NPC가 먼저 데이트를 제안한 경우를 별도 태그로 보존한다.
        # (장기기억 추출 시 중요한 신호)
        if actor == "npc" and action == Action.INVITE_DATE:
            event_log.append("first_date_proposal")

        # 모든 전이 후 상태 안전성 보정 + 단계 재산출.
        s.clamp()
        s.relationship_stage = _stage_from_state(s)

        # 환경 전역 이벤트 로그에 누적한다.
        self.events.extend(event_log)
        return event_log

    def _sanitize_deltas(self, deltas: dict[str, Any]) -> dict[str, int]:
        """LLM delta payload를 안전한 정수 범위로 정규화한다.

        비정상 타입은 0으로 치환하고, 모든 값은 [-10, 10]으로 클램프한다.
        """
        keys = [
            "delta_affection",
            "delta_trust",
            "delta_interest",
            "delta_jealousy",
            "delta_mood",
        ]
        out: dict[str, int] = {}
        for key in keys:
            raw = deltas.get(key, 0)
            val = raw if isinstance(raw, int) else 0
            out[key] = max(-10, min(10, val))
        return out

    def _tag_events_from_action(
        self,
        event_log: list[str],
        *,
        action: Action,
        state: RelationshipState,
    ) -> None:
        """행동/상태를 기반으로 메모리용 이벤트 태그를 부여한다.

        주의:
            이 함수는 "수치 전이"를 결정하지 않는다.
            오직 분석/기억 승격용 태그만 생성한다.
        """
        if action == Action.GIFT:
            event_log.append("gift_received")
        if action == Action.APOLOGIZE:
            event_log.append("apology_made")
        if action == Action.IGNORE:
            event_log.append("ignored")
        if action == Action.TEASE and state.trust < 40:
            event_log.append("first_argument")
        if action == Action.INVITE_DATE:
            if state.relationship_stage in {
                RelationshipStage.FRIEND,
                RelationshipStage.ROMANTIC_INTEREST,
                RelationshipStage.DATING,
                RelationshipStage.RELATIONSHIP,
            }:
                event_log.append("date_invitation_positive")
            else:
                event_log.append("date_invitation_too_early")

    def evaluate_outcome(self) -> str:
        """현재 상태를 종료 조건에 매핑한다.

        Returns:
            - `"success"`: 관계 성립 성공 조건 달성
            - `"failure"`: 관계 붕괴 조건 충족
            - `"ongoing"`: 그 외 진행 중
        """
        s = self.state
        if s.affection > 85 and s.trust > 70 and s.relationship_stage == RelationshipStage.RELATIONSHIP:
            return "success"
        if s.trust < 10 or s.jealousy > 80:
            return "failure"
        return "ongoing"
