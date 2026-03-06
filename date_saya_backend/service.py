from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import sys
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parent

# date_saya_backend 내부에 vendored 된 system 패키지를 최우선으로 사용
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from system.webapi.services import RuntimeServices  # type: ignore  # noqa: E402


def _emotion_dict_to_label(emotion: dict) -> str:
    if not isinstance(emotion, dict):
        return "neutral"
    if int(emotion.get("angry", 0)) > 0:
        return "angry"
    if int(emotion.get("sad", 0)) > 0:
        return "sad"
    if int(emotion.get("happy", 0)) > 0:
        return "happy"
    return "neutral"


def _emotion_to_image_key(emotion_label: str) -> str:
    table = {
        "happy": "smile_saya",
        "sad": "crying_saya",
        "angry": "annoyed_saya",
        "neutral": "neutral_saya",
    }
    return table.get(emotion_label, "neutral_saya")

@dataclass
class SessionState:
    session_id: str
    npc_id: str
    turn: int = 0
    player_name: str = "플레이어"


class DateWithSayaService:
    """date_saya용 서비스.

    핵심:
    - date_saya_backend 내부 vendored `system`의 RuntimeServices를 사용
    - 응답만 Ren'Py 포맷으로 변환
    """

    def __init__(self) -> None:
        # date_saya 모델 경로를 TTS runtime에 주입한다.
        os.environ.setdefault("QWEN_MODEL_DIR", str(PROJECT_ROOT / "date_saya" / "model_assets" / "saya_rp_4b_v3"))
        os.environ.setdefault("TRANS_MODEL_DIR", str(PROJECT_ROOT / "date_saya" / "model_assets" / "qtranslator_1.7b_v2"))
        # vLLM 강제 실패 시 전체가 죽지 않도록 기본은 HF 4bit 경로를 사용.
        os.environ.setdefault("LLM_BACKEND", "hf")
        os.environ.setdefault("LLM_STRICT_VLLM", "0")
        self.runtime = RuntimeServices()
        self.sessions: dict[str, SessionState] = {}
        self._ready: bool = False
        self._startup_error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def startup_error(self) -> Optional[str]:
        return self._startup_error

    def preload(self) -> None:
        """백엔드 시작 시점에 모델/파이프라인을 선로딩한다."""
        if self._ready:
            return
        try:
            # LLM + 번역기 + 메모리/그래프 구성까지 선로딩
            self.runtime._ensure_turn_graph()  # noqa: SLF001

            # 첫 턴 지연을 줄이기 위해 아주 짧은 워밍업 generation 1회 수행
            llm = self.runtime._ensure_llm()  # noqa: SLF001
            prompt = llm.build_prompt(
                [
                    {"role": "system", "content": "너는 사야 역할 챗봇이다."},
                    {"role": "user", "content": "짧게 인사해줘."},
                ]
            )
            raw = llm.generate(prompt)
            if not isinstance(raw, str):
                raise RuntimeError("LLM warmup failed: non-string output.")

            # 필요시 TTS 연결도 시작 시점 점검 가능 (기본 비활성)
            if os.getenv("DATE_SAYA_PRELOAD_TTS", "0") == "1":
                self.runtime._ensure_tts()  # noqa: SLF001

            self._ready = True
            self._startup_error = None
        except Exception as e:
            self._ready = False
            self._startup_error = str(e)
            raise

    def start(self, session_id: str, npc_id: str = "saya") -> SessionState:
        if not self._ready:
            raise RuntimeError(
                f"backend not ready: {self._startup_error or 'preload not completed'}"
            )
        s = SessionState(session_id=session_id, npc_id=npc_id, turn=0)
        self.sessions[session_id] = s
        return s

    def run_turn(
        self,
        session_id: str,
        player_action: str,
        player_text: str = "",
        *,
        player_name: str = "플레이어",
    ) -> dict:
        s = self.sessions.get(session_id)
        if s is None:
            raise KeyError("session not found")
        if player_name and player_name.strip():
            s.player_name = player_name.strip()
        s.turn += 1

        # 실제 이식 경로: RuntimeServices.turn()
        turn_input = player_text.strip() or self._action_to_text(player_action)
        out = self.runtime.turn(
            turn_input,
            style_index=0,
            style_weight=1.0,
            speaker_name="saya",
        )
        emo_label = _emotion_dict_to_label(out.get("emotion", {}))
        options = self._generate_player_options(
            player_action=player_action,
            player_text=turn_input,
            saya_narration=str(out.get("narration", "")),
            saya_dialogue=str(out.get("dialogue_ko", "")),
            player_name=s.player_name,
        )
        return {
            "session_id": session_id,
            "player_action": player_action,
            "player_text": turn_input,
            "saya_text": out.get("rp_text", ""),
            "saya_narration": out.get("narration", ""),
            "saya_dialogue": out.get("dialogue_ko", ""),
            "emotion": emo_label,
            "image_key": _emotion_to_image_key(emo_label),
            "player_options": options,
            "translated_dialogue": out.get("dialogue_ja", out.get("dialogue_ko", "")),
            "wav_path": out.get("wav_path"),
        }

    def _action_to_text(self, action: str) -> str:
        mapping = {
            "talk": "사야에게 말을 건다.",
            "gift": "사야에게 선물을 건넨다.",
            "invite_date": "사야에게 데이트를 제안한다.",
        }
        return mapping.get(action, "사야에게 반응한다.")

    def _generate_player_options(
        self,
        *,
        player_action: str,
        player_text: str,
        saya_narration: str,
        saya_dialogue: str,
        player_name: str,
    ) -> list[str]:
        try:
            llm = self.runtime._ensure_llm()  # noqa: SLF001
            messages = [
                {
                    "role": "system",
                    "content": (
                        "너는 연애 시뮬레이션 플레이어 선택지 생성기다. JSON만 출력한다.\n"
                        '{"options":["...","...","..."]}\n'
                        f"플레이어 이름은 '{player_name}'이다. 선택지 문장에도 이 이름을 자연스럽게 반영하라.\n"
                        "핵심 규칙:\n"
                        "1) 반드시 직전 사야의 서술/대사에 직접 반응하는 내용이어야 한다.\n"
                        "2) 서로 다른 의도(공감/질문/제안 등)로 3개를 만든다.\n"
                        "3) 추상적 문장 금지, 즉시 말할 수 있는 대사형 문장으로 만든다.\n"
                        "4) 한국어, 짧고 실행 가능, 중복 금지."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"플레이어이름={player_name}\n"
                        f"직전 플레이어행동={player_action}\n"
                        f"직전 플레이어텍스트={player_text}\n"
                        f"사야서술={saya_narration}\n"
                        f"사야대사={saya_dialogue}\n"
                        "다음 플레이어 선택지 3개를 생성해라. 반드시 플레이어 이름을 반영하고,\n"
                        "각 선택지는 사야의 직전 말에 대한 반응이어야 한다."
                    ),
                },
            ]
            prompt = llm.build_prompt(messages)
            raw = llm.generate(prompt)
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                opts = data.get("options")
                if isinstance(opts, list):
                    out = [str(x).strip() for x in opts if str(x).strip()]
                    if len(out) >= 3:
                        return out[:3]
        except Exception:
            pass
        return [
            f"{player_name}, 방금 말해준 부분에서 네가 특히 불안했던 지점이 뭐야?",
            f"{player_name}, 네 말 들으니까 이해돼. 그럼 내가 천천히 맞춰볼게.",
            f"{player_name}, 지금 분위기 괜찮으면 짧게 같이 할 수 있는 걸 하나 정해볼까?",
        ]
