# Date With Saya Backend

Ren'Py(`date_saya`)에서 호출하는 LLM 오케스트레이션 백엔드.

구성:
- `FastAPI` 얇은 래퍼
- 핵심 파이프라인은 `date_saya_backend/system`의 `RuntimeServices`를 사용
- 대사 파싱/번역/감정/TTS/메모리(`SQLite`, `sqlite-vec`)는 vendored `system` 모듈에서 처리
- 로컬 ONNX TTS 런타임: `date_saya_backend/sbv_runtime`

## Run

프로젝트 루트(`RomanceArena`)에서:

```bash
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

Ren'Py는 기본으로 `http://127.0.0.1:8010`을 호출한다.

Ren'Py + 백엔드 동시 실행(자동 기동):

```bash
cd /home/hosung/pytorch-demo/RomanceArena/date_saya
./run_with_backend.sh
```

기본은 `LLM_BACKEND=hf`(4bit) 경로이며, 런처의 vLLM 자동 기동은 기본 OFF(`DATE_SAYA_START_LLM=0`).

로컬 TTS 런타임 단독 테스트:

```bash
uv run python -m date_saya_backend.sbv_runtime --help
```

## Env

- `DATE_SAYA_LLM_BASE_URL` (default: `http://127.0.0.1:8100/v1`)
- `DATE_SAYA_LLM_MODEL` (default: `saya-rp-4b`)
- `DATE_SAYA_LLM_API_KEY` (default: `dummy`)
- `DATE_SAYA_MEMORY_DB` (default: `date_saya/outputs/date_saya_memory.sqlite3`)
- `DATE_SAYA_TRANSLATOR_URL` (optional)
- `DATE_SAYA_TTS_URL` (optional)

옵션 API 포맷:
- Translator: `POST` body `{"text_ko":"..."}` -> response `{"text_ja":"..."}`
- TTS: `POST` body `{"text_ja":"...", "speaker_name":"saya"}` -> response `{"wav_path":"..."}`
