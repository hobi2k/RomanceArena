from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import httpx
import json
import os
import re
from typing import Optional

from .fsm import (
    FsmTransitionInput,
    post_adjust_saya_fsm,
    saya_fsm_policy_text,
    transition_saya_fsm,
)
from .memory_chain import SummaryMemoryChain, SummaryMemoryConfig
from .pipeline import build_turn_graph
from .parser import emotion_to_image_key
from .session_store import SessionStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class SessionState:
    """세션 상태 레코드.

    Args:
        session_id: 세션 식별자.
        npc_id: 대상 NPC 식별자.
        turn: 현재 턴 번호.
        player_name: Ren'Py에서 전달된 플레이어 이름.

    Returns:
        SessionState: 메모리에 보관되는 세션 상태 객체.
    """
    session_id: str
    npc_id: str
    turn: int = 0
    player_name: str = "플레이어"
    saved: bool = False
    npc_emotion: str = "neutral"
    saya_fsm_state: str = "guarded"

class LocalLLM:
    """백엔드 전용 vLLM OpenAI-compatible 클라이언트.

    Args:
        없음.

    Returns:
        LocalLLM: `saya_rp_4b_v3` 호출과 function calling 판정을 담당하는 클라이언트.
    """

    def __init__(self) -> None:
        """LLM 클라이언트 내부 상태를 초기화한다.

        Args:
            없음.

        Returns:
            None.
        """
        self.base_url = os.getenv("DATE_SAYA_LLM_BASE_URL", "http://127.0.0.1:8100")
        self.model_name = os.getenv("DATE_SAYA_LLM_MODEL_NAME", "saya-rp-4b")
        self.max_new_tokens = int(os.getenv("DATE_SAYA_LLM_MAX_NEW_TOKENS", "220"))
        self.temperature = float(os.getenv("DATE_SAYA_LLM_TEMPERATURE", "0.75"))
        self.timeout = float(os.getenv("DATE_SAYA_LLM_TIMEOUT", "120"))
        self._client: Optional[httpx.Client] = None

    def preload(self) -> None:
        """서비스 기동 전에 vLLM 엔드포인트 연결 가능 여부를 확인한다.

        Args:
            없음.

        Returns:
            None.
        """
        client = self._get_client()
        resp = client.get(f"{self.base_url.rstrip('/')}/v1/models")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            raise RuntimeError(f"invalid /v1/models response: {data}")

    def _get_client(self) -> httpx.Client:
        """공유 HTTP 클라이언트를 생성하거나 반환한다.

        Args:
            없음.

        Returns:
            httpx.Client: OpenAI-compatible endpoint 호출용 클라이언트.
        """
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
    ) -> dict:
        """OpenAI-compatible chat completions를 호출한다.

        Args:
            messages: OpenAI chat messages.
            max_tokens: 최대 생성 토큰.
            temperature: 샘플링 온도.
            tools: function calling tool schema 목록.
            tool_choice: 강제 도구 선택 정책.

        Returns:
            dict: `/v1/chat/completions` 응답 JSON.
        """
        self.preload()
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": min(max_tokens, self.max_new_tokens),
            "temperature": temperature,
            "top_p": 0.92,
            "repetition_penalty": 1.05,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        client = self._get_client()
        resp = client.post(f"{self.base_url.rstrip('/')}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    def chat_tool(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict,
        tool_name: str,
        max_tokens: int = 180,
        temperature: float = 0.8,
    ) -> dict:
        """실제 function calling 경로로 도구 인자 JSON을 생성한다.

        Args:
            system_prompt: 시스템 프롬프트.
            user_prompt: 사용자 프롬프트.
            tool_schema: JSON 판정에 사용할 함수 스키마 설명.
            tool_name: 강제 호출할 함수명.
            max_tokens: 생성 토큰 상한.
            temperature: 샘플링 온도.

        Returns:
            dict: tool call arguments JSON.
        """
        response = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            tools=[tool_schema],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        choices = response.get("choices", [])
        if not choices:
            raise RuntimeError(f"tool call response missing choices: {response}")
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            raise RuntimeError(f"tool call missing in response: {response}")
        function = tool_calls[0].get("function", {})
        if function.get("name") != tool_name:
            raise RuntimeError(f"unexpected tool selected: {function}")
        args_raw = function.get("arguments", "")
        if not isinstance(args_raw, str) or not args_raw.strip():
            raise RuntimeError(f"tool arguments missing: {function}")
        try:
            return json.loads(args_raw)
        except Exception as e:
            raise RuntimeError(f"tool arguments parse failed: {args_raw}") from e

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 180, temperature: float = 0.75) -> str:
        """일반 채팅 생성 공통 진입점.

        Args:
            system_prompt: 시스템 프롬프트.
            user_prompt: 사용자 프롬프트.
            max_tokens: 최대 생성 토큰.
            temperature: 샘플링 온도.

        Returns:
            str: 모델 생성 결과 텍스트.
        """
        response = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choices = response.get("choices", [])
        if not choices:
            raise RuntimeError(f"chat response missing choices: {response}")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")).strip())
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()


class DateWithSayaService:
    """Date With Saya 턴 처리 서비스.

    Args:
        없음.

    Returns:
        DateWithSayaService: 세션/그래프/LLM을 관리하는 서비스 객체.
    """

    def __init__(self) -> None:
        """서비스를 구성한다.

        Args:
            없음.

        Returns:
            None.
        """
        self.sessions: dict[str, SessionState] = {}
        self._ready: bool = False
        self._startup_error: Optional[str] = None
        session_db = Path(
            os.getenv(
                "DATE_SAYA_SESSION_DB",
                str(PROJECT_ROOT / "date_saya_backend" / "outputs" / "sessions.sqlite3"),
            )
        )
        self.store = SessionStore(session_db)
        self.llm = LocalLLM()
        memory_db = Path(
            os.getenv(
                "DATE_SAYA_MEMORY_DB",
                str(PROJECT_ROOT / "date_saya_backend" / "outputs" / "memory" / "memory.sqlite3"),
            )
        )
        self.memory = SummaryMemoryChain(
            llm_chat=self.llm.chat,
            config=SummaryMemoryConfig(
                db_path=str(memory_db),
                update_every_turns=int(os.getenv("DATE_SAYA_MEMORY_UPDATE_EVERY", "1")),
                recent_turn_window=int(os.getenv("DATE_SAYA_MEMORY_RECENT_WINDOW", "6")),
                retrieval_limit=int(os.getenv("DATE_SAYA_MEMORY_RETRIEVAL_LIMIT", "8")),
                promote_threshold=float(os.getenv("DATE_SAYA_MEMORY_PROMOTE_THRESHOLD", "0.65")),
                vector_dim=int(os.getenv("DATE_SAYA_MEMORY_VECTOR_DIM", "1024")),
                max_summary_chars=int(os.getenv("DATE_SAYA_MEMORY_MAX_SUMMARY_CHARS", "1200")),
            ),
        )
        self._turn_graph = build_turn_graph(
            llm_chat=self.llm.chat,
            infer_emotion=self._infer_emotion,
            generate_player_options=self._generate_player_options,
            build_memory_context=self._build_memory_context,
        )

    @property
    def ready(self) -> bool:
        """서비스 준비 상태를 조회한다.

        Args:
            없음.

        Returns:
            bool: preload 완료 여부.
        """
        return self._ready

    @property
    def startup_error(self) -> Optional[str]:
        """초기화 오류 메시지를 조회한다.

        Args:
            없음.

        Returns:
            Optional[str]: 마지막 preload 실패 원인.
        """
        return self._startup_error

    def preload(self) -> None:
        """서비스 구동 전 선로딩을 수행한다.

        Args:
            없음.

        Returns:
            None.
        """
        if self._ready:
            return
        try:
            # 요구사항: 저장하지 않은 세션은 다음 실행에서 폐기한다.
            self.store.delete_unsaved()
            self.llm.preload()
            self._ready = True
            self._startup_error = None
        except Exception as e:
            self._ready = False
            self._startup_error = str(e)
            raise

    def start(self, session_id: str, npc_id: str = "saya") -> SessionState:
        """새 세션을 생성한다.

        Args:
            session_id: 세션 식별자.
            npc_id: 대상 NPC 식별자.

        Returns:
            SessionState: 생성된 세션 상태.
        """
        if not self._ready:
            raise RuntimeError(f"backend not ready: {self._startup_error or 'preload not completed'}")
        s = SessionState(session_id=session_id, npc_id=npc_id, turn=0, saved=False)
        self.sessions[session_id] = s
        self.store.upsert(
            session_id=s.session_id,
            npc_id=s.npc_id,
            turn=s.turn,
            player_name=s.player_name,
            saved=s.saved,
            npc_emotion=s.npc_emotion,
            saya_fsm_state=s.saya_fsm_state,
        )
        return s

    def _get_or_restore_session(self, session_id: str) -> Optional[SessionState]:
        """메모리 세션을 우선 사용하고, 없으면 저장소에서 복구한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            Optional[SessionState]: 복구 성공 시 세션 객체, 없으면 None.
        """
        s = self.sessions.get(session_id)
        if s is not None:
            return s
        row = self.store.get(session_id)
        if row is None:
            return None
        s = SessionState(
            session_id=row.session_id,
            npc_id=row.npc_id,
            turn=row.turn,
            player_name=row.player_name,
            saved=row.saved,
            npc_emotion=row.npc_emotion,
            saya_fsm_state=row.saya_fsm_state,
        )
        self.sessions[session_id] = s
        return s

    def run_turn(
        self,
        session_id: str,
        player_action: str,
        player_text: str = "",
        *,
        player_name: str = "플레이어",
        player_love: int = 0,
        player_rel: str = "Stranger",
        player_charm: int = 0,
        player_intel: int = 0,
        player_create: int = 0,
    ) -> dict:
        """한 턴을 실행하고 API 응답용 결과를 만든다.

        Args:
            session_id: 현재 세션 식별자.
            player_action: 플레이어 행동 타입.
            player_text: 플레이어 입력 텍스트.
            player_name: Ren'Py 사용자 이름.

        Returns:
            dict: API 스키마와 동일한 턴 결과 딕셔너리.
        """
        s = self._get_or_restore_session(session_id)
        if s is None:
            raise KeyError("session not found")
        if player_name and player_name.strip():
            s.player_name = player_name.strip()
        s.turn += 1

        turn_input = player_text.strip() or self._action_to_text(player_action)
        action_result, date_accepted, affection_delta = self._resolve_action(
            player_action=player_action,
            player_love=int(player_love),
            player_rel=str(player_rel),
            npc_emotion=s.npc_emotion,
            player_text=turn_input,
            player_charm=int(player_charm),
            player_intel=int(player_intel),
            player_create=int(player_create),
        )
        next_fsm_state = transition_saya_fsm(
            FsmTransitionInput(
                current_state=s.saya_fsm_state,
                player_action=player_action,
                action_result=action_result,
                date_accepted=date_accepted,
                affection_delta=affection_delta,
                npc_emotion=s.npc_emotion,
                player_rel=str(player_rel),
            )
        )
        fsm_policy = saya_fsm_policy_text(next_fsm_state)

        state = self._turn_graph.invoke(
            {
                "session_id": session_id,
                "turn_idx": s.turn,
                "player_action": player_action,
                "player_text": turn_input,
                "player_name": s.player_name,
                "action_result": action_result,
                "date_accepted": date_accepted,
                "affection_delta": affection_delta,
                "fsm_state": next_fsm_state,
                "fsm_policy": fsm_policy,
            }
        )
        final_fsm_state = post_adjust_saya_fsm(
            base_state=next_fsm_state,
            current_emotion=state.get("emotion", "neutral"),
        )
        self.memory.update(
            session_id=session_id,
            user_text=turn_input,
            assistant_text=state.get("rp_raw", ""),
        )

        self.store.upsert(
            session_id=s.session_id,
            npc_id=s.npc_id,
            turn=s.turn,
            player_name=s.player_name,
            saved=s.saved,
            npc_emotion=state.get("emotion", s.npc_emotion),
            saya_fsm_state=final_fsm_state,
        )
        s.npc_emotion = state.get("emotion", s.npc_emotion)
        s.saya_fsm_state = final_fsm_state

        return {
            "session_id": session_id,
            "player_action": player_action,
            "player_text": turn_input,
            "saya_text": state.get("rp_raw", ""),
            "saya_narration": state.get("narration", ""),
            "saya_dialogue": state.get("dialogue", ""),
            "emotion": state.get("emotion", "neutral"),
            "image_key": emotion_to_image_key(state.get("emotion", "neutral")),
            "player_options": state.get("player_options", []),
            "translated_dialogue": state.get("dialogue", ""),
            "wav_path": None,
            "action_result": action_result,
            "date_accepted": date_accepted,
            "affection_delta": int(affection_delta),
            "saya_fsm_state": final_fsm_state,
        }

    def memory_status(self) -> dict:
        """장기기억 체인 상태를 조회한다.

        Args:
            없음.

        Returns:
            dict: 메모리 DB/벡터 설정 상태.
        """
        return self.memory.status()

    def mark_session_saved(self, session_id: str) -> bool:
        """세션을 저장 완료 상태로 마킹한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            bool: 마킹 성공 여부.
        """
        s = self._get_or_restore_session(session_id)
        if s is not None:
            s.saved = True
        ok = self.store.mark_saved(session_id)
        return ok

    def discard_session(self, session_id: str) -> bool:
        """세션을 메모리/저장소에서 삭제한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            bool: 삭제 성공 여부.
        """
        self.sessions.pop(session_id, None)
        return self.store.delete(session_id)
    def _infer_emotion(self, *, narration: str, dialogue: str) -> str:
        """사야 서술/대사를 바탕으로 감정 라벨을 판정한다.

        Args:
            narration: 사야 서술 텍스트.
            dialogue: 사야 대사 텍스트.

        Returns:
            str: `happy|sad|angry|neutral` 중 하나.
        """
        raw = self.llm.chat(
            system_prompt=(
                "너는 감정 판정기다. 반드시 JSON만 출력한다.\n"
                '{"emotion":"happy|sad|angry|neutral","reason":"짧은 근거"}\n'
            ),
            user_prompt=f"사야 서술: {narration}\n사야 대사: {dialogue}\n감정을 판정해.",
            max_tokens=80,
            temperature=0.2,
        )
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise RuntimeError(f"emotion json parse failed: {raw}")
        data = json.loads(m.group(0))
        emo = str(data.get("emotion", "")).strip().lower()
        if emo not in {"happy", "sad", "angry", "neutral"}:
            raise RuntimeError(f"invalid emotion label: {emo}")
        return emo

    def _action_to_text(self, action: str) -> str:
        """행동 타입을 기본 입력 문장으로 변환한다.

        Args:
            action: 행동 타입 문자열.

        Returns:
            str: LLM 입력용 기본 문장.
        """
        mapping = {
            "talk": "사야에게 말을 건다.",
            "gift": "사야에게 선물을 건넨다.",
            "invite_date": "사야에게 데이트를 제안한다.",
        }
        return mapping.get(action, "사야에게 반응한다.")

    def _resolve_action(
        self,
        *,
        player_action: str,
        player_love: int,
        player_rel: str,
        npc_emotion: str,
        player_text: str,
        player_charm: int,
        player_intel: int,
        player_create: int,
    ) -> tuple[str, bool, int]:
        """액션 결과를 계산한다. gift/invite_date는 LLM JSON 판정으로 처리한다.

        Args:
            player_action: 플레이어 행동 타입.
            player_love: 현재 호감도.
            player_rel: 현재 관계 단계.
            npc_emotion: NPC 직전 감정.
            player_text: 플레이어 입력 텍스트.
            player_charm: 플레이어 charm 스탯.
            player_intel: 플레이어 intel 스탯.
            player_create: 플레이어 create 스탯.

        Returns:
            tuple[str, bool, int]: (action_result, date_accepted, affection_delta)
        """
        rel = (player_rel or "").strip()
        love = int(player_love)
        emo = (npc_emotion or "neutral").strip().lower()
        charm = int(player_charm)
        intel = int(player_intel)
        create = int(player_create)

        if player_action == "talk":
            if rel == "Stranger":
                base = 4
            elif rel == "Friend":
                base = 6
            else:
                base = 5
            # talk은 creativity(create) 스탯만 영향.
            bonus = 0
            if create >= 12:
                bonus = 3
            elif create >= 8:
                bonus = 2
            elif create >= 4:
                bonus = 1
            delta = max(-10, min(15, base + bonus))
            if rel == "Stranger":
                return ("talk_cautious_progress", False, delta)
            if rel == "Friend":
                return ("talk_build_intimacy", False, delta)
            return ("talk_deepen_bond", False, delta)

        if player_action == "gift":
            tool_name = "judge_gift_reaction"
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": "선물 액션의 수용/거절 맥락과 호감도 변화를 판정한다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_result": {
                                "type": "string",
                                "description": "gift_too_early|gift_polite_refusal|gift_well_received|gift_romantic_success",
                            },
                            "date_accepted": {
                                "type": "boolean",
                                "description": "gift에서는 항상 false를 반환한다.",
                            },
                            "affection_delta": {
                                "type": "integer",
                                "description": "호감도 변화량(-10~15)",
                            },
                        },
                        "required": ["action_result", "date_accepted", "affection_delta"],
                    },
                },
            }
            judged = self.llm.chat_tool(
                system_prompt="""
                    너는 연애 시뮬레이션 판정기다.
                    목적: 플레이어의 선물 행동에 대한 NPC 반응을 감정/관계 기반으로 확률적으로 판정한다.
                    반드시 function call만 수행한다.
                    규칙:
                    - 감정이 angry/sad이고 친밀도 낮으면 거절/보류 확률을 높인다.
                    - 관계 단계와 호감도(love)가 높으면 긍정 반응 확률을 높인다.
                    - action_result는 정의된 값 중 하나여야 한다.
                    - date_accepted는 gift 액션에서 항상 false다.
                    - affection_delta는 -10~15 범위 정수.
                """,
                user_prompt=f"""
                    player_action=gift
                    player_rel={rel}
                    player_love={love}
                    npc_emotion={emo}
                    player_charm={charm}
                    player_intel={intel}
                    player_create={create}
                    player_text={player_text}
                """,
                tool_schema=tool_schema,
                tool_name=tool_name,
                max_tokens=120,
                temperature=0.9,
            )
            action_result = str(judged.get("action_result", "")).strip()
            delta = int(judged.get("affection_delta", 0))
            delta = max(-10, min(15, delta))
            if not action_result:
                raise RuntimeError(f"gift judgement missing action_result: {judged}")
            return (action_result, False, delta)

        if player_action == "invite_date":
            tool_name = "judge_date_invitation"
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": "데이트 제안 수락 여부와 호감도 변화를 판정한다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_result": {
                                "type": "string",
                                "description": "date_accept_confident|date_accept_cautious|date_reject_too_early|date_reject_mood",
                            },
                            "date_accepted": {"type": "boolean"},
                            "affection_delta": {
                                "type": "integer",
                                "description": "호감도 변화량(-10~15)",
                            },
                        },
                        "required": ["action_result", "date_accepted", "affection_delta"],
                    },
                },
            }
            judged = self.llm.chat_tool(
                system_prompt="""
                    너는 연애 시뮬레이션 판정기다.
                    목적: 플레이어의 데이트 제안을 NPC 감정 상태 기반으로 확률적으로 판정한다.
                    반드시 function call만 수행한다.
                    규칙:
                    - charm이 높을수록 수락 확률을 유의미하게 높인다.
                    - charm이 낮으면 같은 조건에서도 거절 확률을 높인다.
                    - 감정이 sad/angry면 거절 확률을 높인다.
                    - 관계 단계와 호감도(love)가 높으면 수락 확률을 높인다.
                    - affection_delta는 -10~15 범위 정수.
                """,
                user_prompt=f"""
                    player_action=invite_date
                    player_rel={rel}
                    player_love={love}
                    npc_emotion={emo}
                    player_charm={charm}
                    player_intel={intel}
                    player_create={create}
                    player_text={player_text}
                """,
                tool_schema=tool_schema,
                tool_name=tool_name,
                max_tokens=120,
                temperature=0.9,
            )
            action_result = str(judged.get("action_result", "")).strip()
            accepted = bool(judged.get("date_accepted", False))
            delta = int(judged.get("affection_delta", 0))
            # invite_date는 charm이 결과 강도에 직접 영향.
            if charm >= 12:
                delta += 3
            elif charm >= 8:
                delta += 2
            elif charm <= 2:
                delta -= 2
            delta = max(-10, min(15, delta))
            if not action_result:
                raise RuntimeError(f"invite_date judgement missing action_result: {judged}")
            return (action_result, accepted, delta)

        return ("generic_response", False, 0)

    def _build_memory_context(self, *, session_id: str, current_user_text: str) -> str:
        """턴 생성에 주입할 메모리 컨텍스트를 만든다.

        Args:
            session_id: 세션 식별자.
            current_user_text: 현재 플레이어 텍스트.

        Returns:
            str: 메모리 컨텍스트 문자열.
        """
        return self.memory.build_memory_context(
            session_id=session_id,
            current_user_text=current_user_text,
        )

    def _generate_player_options(
        self,
        *,
        player_action: str,
        player_text: str,
        saya_narration: str,
        saya_dialogue: str,
        player_name: str,
    ) -> list[str]:
        """사야 응답을 기반으로 반응형 선택지 3개를 생성한다.

        Args:
            player_action: 직전 플레이어 행동.
            player_text: 직전 플레이어 텍스트.
            saya_narration: 사야 서술 텍스트.
            saya_dialogue: 사야 대사 텍스트.
            player_name: 플레이어 이름.

        Returns:
            list[str]: UI에 표시할 선택지 3개.
        """
        raw = self.llm.chat(
            system_prompt=(
                "너는 연애 시뮬레이션의 플레이어 선택지 생성기다. JSON만 출력한다.\n"
                '{"options":["...","...","..."]}\n'
                "규칙: 사야의 직전 발화에 직접 반응, 3개 의도는 서로 다르게(공감/질문/제안), 짧고 실행 가능."
            ),
            user_prompt=(
                f"플레이어이름={player_name}\n"
                f"직전 플레이어행동={player_action}\n"
                f"직전 플레이어텍스트={player_text}\n"
                f"사야서술={saya_narration}\n"
                f"사야대사={saya_dialogue}\n"
                "선택지 3개를 JSON으로 생성해."
            ),
            max_tokens=140,
            temperature=0.6,
        )
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise RuntimeError(f"options json parse failed: {raw}")
        data = json.loads(m.group(0))
        opts = data.get("options")
        if not isinstance(opts, list):
            raise RuntimeError(f"options payload invalid: {data}")
        out = [str(x).strip() for x in opts if str(x).strip()]
        if len(out) < 3:
            raise RuntimeError(f"insufficient options: {out}")
        return out[:3]
