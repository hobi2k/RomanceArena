from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class VLLMRuntimeConfig:
    """vLLM 런타임 설정.

    Args:
        model_path: 로컬 Qwen RP 모델 경로.
        host: vLLM OpenAI API 바인드 호스트.
        port: vLLM OpenAI API 포트.
        served_model_name: OpenAI API에서 사용할 모델 이름.
        auto_start: 백엔드 기동 시 vLLM 자동 실행 여부.
        max_model_len: vLLM 최대 컨텍스트 길이.
        gpu_memory_utilization: GPU 메모리 사용 비율.
        max_num_seqs: 동시 시퀀스 수.
        tool_call_parser: vLLM tool parser 이름.
        quantization: 양자화 모드.
        load_format: 가중치 로드 포맷.

    Returns:
        VLLMRuntimeConfig: 환경변수 기반 설정 객체.
    """

    model_path: str
    host: str
    port: int
    served_model_name: str
    auto_start: bool
    max_model_len: int
    gpu_memory_utilization: float
    max_num_seqs: int
    tool_call_parser: str
    quantization: str
    load_format: str

    @staticmethod
    def from_env() -> "VLLMRuntimeConfig":
        """환경변수에서 런타임 설정을 읽는다.

        Args:
            없음.

        Returns:
            VLLMRuntimeConfig: 파싱된 설정.
        """
        return VLLMRuntimeConfig(
            model_path=os.getenv(
                "DATE_SAYA_LLM_MODEL_PATH",
                str(PROJECT_ROOT / "date_saya_backend" / "model_assets" / "saya_rp_4b_v3"),
            ),
            host=os.getenv("DATE_SAYA_LLM_HOST", "127.0.0.1"),
            port=int(os.getenv("DATE_SAYA_LLM_PORT", "8100")),
            served_model_name=os.getenv("DATE_SAYA_LLM_MODEL_NAME", "saya-rp-4b"),
            auto_start=os.getenv("DATE_SAYA_AUTO_START_VLLM", "1") == "1",
            max_model_len=int(os.getenv("DATE_SAYA_LLM_MAX_MODEL_LEN", "1536")),
            gpu_memory_utilization=float(os.getenv("DATE_SAYA_LLM_GPU_MEMORY_UTILIZATION", "0.85")),
            max_num_seqs=int(os.getenv("DATE_SAYA_LLM_MAX_NUM_SEQS", "1")),
            tool_call_parser=os.getenv("DATE_SAYA_LLM_TOOL_CALL_PARSER", "qwen3_xml"),
            quantization=os.getenv("DATE_SAYA_LLM_QUANTIZATION", "bitsandbytes"),
            load_format=os.getenv("DATE_SAYA_LLM_LOAD_FORMAT", "bitsandbytes"),
        )


class VLLMRuntimeManager:
    """date_saya_backend 전용 vLLM 런타임 관리자.

    Args:
        cfg: 환경변수 기반 설정. 없으면 기본값 사용.

    Returns:
        VLLMRuntimeManager: vLLM 프로세스를 기동/종료하는 관리자.
    """

    def __init__(self, cfg: Optional[VLLMRuntimeConfig] = None) -> None:
        self.cfg = cfg or VLLMRuntimeConfig.from_env()
        self._proc: Optional[subprocess.Popen[str]] = None

    def _models_url(self) -> str:
        """vLLM 모델 목록 엔드포인트 URL을 만든다.

        Args:
            없음.

        Returns:
            str: `/v1/models` URL.
        """
        return f"http://{self.cfg.host}:{self.cfg.port}/v1/models"

    def is_ready(self) -> bool:
        """vLLM OpenAI API 준비 상태를 확인한다.

        Args:
            없음.

        Returns:
            bool: API가 응답하고 모델 목록을 반환하면 True.
        """
        try:
            with urllib.request.urlopen(self._models_url(), timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return isinstance(data, dict) and "data" in data
        except Exception:
            return False

    def start(self) -> None:
        """vLLM 서버를 시작하고 준비 완료까지 대기한다.

        Args:
            없음.

        Returns:
            None.
        """
        if self.is_ready():
            return
        if not self.cfg.auto_start:
            raise RuntimeError(
                "DATE_SAYA_AUTO_START_VLLM=0 이고 vLLM 서버가 준비되지 않았습니다. "
                f"expected={self._models_url()}"
            )

        model_dir = Path(self.cfg.model_path)
        if not model_dir.exists():
            raise RuntimeError(f"LLM model path not found: {model_dir}")

        cmd = [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--host",
            self.cfg.host,
            "--port",
            str(self.cfg.port),
            "--model",
            str(model_dir),
            "--served-model-name",
            self.cfg.served_model_name,
            "--max-model-len",
            str(self.cfg.max_model_len),
            "--gpu-memory-utilization",
            str(self.cfg.gpu_memory_utilization),
            "--max-num-seqs",
            str(self.cfg.max_num_seqs),
            "--enable-auto-tool-choice",
            "--tool-call-parser",
            self.cfg.tool_call_parser,
        ]
        if self.cfg.quantization and self.cfg.quantization.lower() != "none":
            cmd.extend(["--quantization", self.cfg.quantization])
        if self.cfg.load_format and self.cfg.load_format.lower() != "auto":
            cmd.extend(["--load-format", self.cfg.load_format])

        env = os.environ.copy()
        env.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

        self._proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
        )

        for _ in range(180):
            if self._proc.poll() is not None:
                raise RuntimeError("vLLM process terminated during startup.")
            if self.is_ready():
                return
            time.sleep(1)
        raise RuntimeError("vLLM server did not become ready in time.")

    def stop(self) -> None:
        """이 런타임 매니저가 직접 띄운 vLLM 프로세스를 종료한다.

        Args:
            없음.

        Returns:
            None.
        """
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._proc = None
