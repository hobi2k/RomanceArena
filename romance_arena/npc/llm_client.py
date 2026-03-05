from __future__ import annotations

"""OpenAI 호환 API 클라이언트.

이 모듈은 NPC 에이전트가 사용하는 공통 LLM 호출 계층이다.
function-calling(`tools`)과 일반 텍스트 생성을 모두 제공한다.
"""

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv


class OpenAICompatFunctionCaller:
    """OpenAI/vLLM 호환 function-calling 클라이언트.

    환경 변수:
    - ROMANCE_LLM_MODE: `openai_compat` 또는 `mock`
    - ROMANCE_LLM_BASE_URL: OpenAI 호환 엔드포인트(`/v1`) 기준 base URL
    - ROMANCE_LLM_MODEL: 모델 식별자
    - ROMANCE_LLM_API_KEY: 선택(없어도 로컬 vLLM은 동작 가능)
    - ROMANCE_LLM_TIMEOUT: 요청 타임아웃(초)
    - ROMANCE_LLM_RETRIES: 재시도 횟수
    """

    def __init__(self) -> None:
        # openai_compat 모드 사용 시 .env 기반 설정을 우선 로드한다.
        load_dotenv(override=False)
        self.mode = os.getenv("ROMANCE_LLM_MODE", "mock").strip().lower()
        self.base_url = os.getenv("ROMANCE_LLM_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
        self.model = os.getenv("ROMANCE_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        self.api_key = os.getenv("ROMANCE_LLM_API_KEY", "")
        self.timeout_sec = float(os.getenv("ROMANCE_LLM_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("ROMANCE_LLM_RETRIES", "2"))

    def enabled(self) -> bool:
        """실제 API 호출 모드 여부."""
        return self.mode == "openai_compat"

    def choose_action_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """function-calling(JSON tool args) 응답을 받아 dict로 반환한다."""
        if not self.enabled():
            raise RuntimeError("LLM function-calling is disabled (mode != openai_compat).")

        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "tools": [{"type": "function", "function": tool_schema}],
            "tool_choice": {"type": "function", "function": {"name": tool_schema["name"]}},
            "temperature": 0.2,
        }

        data = self._post_json(url=url, headers=headers, body=body)
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices in LLM response.")

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            raise ValueError("No tool_calls in LLM response.")

        function = tool_calls[0].get("function", {})
        args_text = function.get("arguments", "{}")
        try:
            payload = json.loads(args_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid function arguments JSON: {args_text}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Function arguments must be JSON object.")
        return payload

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.6,
        max_tokens: int = 120,
    ) -> str:
        """일반 텍스트 생성(chat/completions) 결과를 반환한다."""
        if not self.enabled():
            raise RuntimeError("LLM text generation is disabled (mode != openai_compat).")

        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post_json(url=url, headers=headers, body=body)
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices in text generation response.")
        message = choices[0].get("message", {})
        text = message.get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Empty content in text generation response.")
        return text.strip()

    def _post_json(self, *, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        """HTTP POST + JSON 응답 파싱 + 재시도 래퍼."""
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_sec) as client:
                    res = client.post(url, headers=headers, json=body)
                    res.raise_for_status()
                    data = res.json()
                if not isinstance(data, dict):
                    raise ValueError("LLM response is not JSON object.")
                return data
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"LLM request failed after retries: {last_error}")
