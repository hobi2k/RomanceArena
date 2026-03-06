# RomanceArena

현재 메인 실행 대상은 `date_saya`(Ren'Py 클라이언트) + `date_saya_backend`(FastAPI/LangGraph 백엔드) 조합이다.

## 현재 구조

- `date_saya/`
  - Ren'Py 게임 프로젝트
  - 화면/라벨/이미지/선택지 UI
  - `run_with_backend.sh`: Ren'Py 실행 시 백엔드(+옵션 LLM) 자동 기동 런처
- `date_saya_backend/`
  - FastAPI API (`/start`, `/turn`, `/health`)
  - LangGraph 턴 파이프라인
  - SQLite 메모리 + sqlite-vec(가능 시)
  - 사야 NPC 응답 생성 + 감정 라벨 + 플레이어 선택지 생성
  - `sbv_runtime/` ONNX TTS 런타임
- `romance_arena/`
  - 초기/실험용 전략 배틀 엔진(레거시 참고 코드)

## 실행 (권장)

```bash
cd /home/hosung/pytorch-demo/RomanceArena/date_saya
./run_with_backend.sh
```

```bash
cd date_saya && ./run_with_backend.sh
```

런처 동작:
1. (옵션) 로컬 vLLM 서버 시작 (`127.0.0.1:8100`)
2. FastAPI 백엔드 시작 (`127.0.0.1:8010`)
3. 헬스체크 통과 후 Ren'Py 실행
4. 종료 시 백엔드/LLM 프로세스 정리

## 수동 실행

백엔드만:

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

Ren'Py:

```bash
/home/hosung/pytorch-demo/renpy-8.3.0-sdk/renpy.sh /home/hosung/pytorch-demo/RomanceArena/date_saya
```

## 환경변수

런처 주요 변수:

- `DATE_SAYA_START_LLM` (`1|0`, 기본 `1`)
- `DATE_SAYA_LLM_MODEL_PATH` (기본 `date_saya/model_assets/saya_rp_4b_v3`)
- `DATE_SAYA_LLM_SERVED_MODEL_NAME` (기본 `saya-rp-4b`)
- `DATE_SAYA_LLM_MAX_MODEL_LEN` (기본 `1536`)
- `DATE_SAYA_LLM_GPU_UTIL` (기본 `0.85`)

백엔드 주요 변수:

- `DATE_SAYA_LLM_BASE_URL` (기본 `http://127.0.0.1:8100/v1`)
- `DATE_SAYA_LLM_MODEL` (기본 `saya-rp-4b`)
- `DATE_SAYA_MEMORY_DB`
- `DATE_SAYA_TRANSLATOR_URL` (옵션)
- `DATE_SAYA_TTS_URL` (옵션)

## 문서

- 설계 문서: [Romance_Arena.md](/home/hosung/pytorch-demo/RomanceArena/Romance_Arena.md)
- 백엔드 상세: [date_saya_backend/README.md](/home/hosung/pytorch-demo/RomanceArena/date_saya_backend/README.md)
