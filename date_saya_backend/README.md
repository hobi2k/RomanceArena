# Date Saya Backend

`date_saya_backend`는 Ren'Py(`date_saya`)가 호출하는 게임 서버다.  
역할은 단순 텍스트 생성이 아니라, 액션 판정 + 대사 생성 + 감정 추론 + 메모리 업데이트를 한 턴 단위로 처리하는 것이다.

## 1. 역할 분리

- `api.py`
  - FastAPI 엔드포인트 정의
  - lifespan에서 `runtime.start()` + `service.preload()` 수행
- `runtime.py`
  - `saya_rp_4b_v3`를 vLLM OpenAI-compatible 서버로 자동 기동
  - `/v1/models` 준비 상태 확인 및 종료 처리
- `service.py`
  - 세션 관리
  - 액션 판정
  - vLLM OpenAI-compatible 호출(일반 chat + function calling)
  - LangGraph 실행
  - 메모리 체인 업데이트
- `pipeline.py`
  - 턴 그래프(`memory -> generate -> parse -> emotion -> options`)
- `memory_chain.py`
  - sqlite-vec 기반 장기기억 저장/검색
- `session_store.py`
  - 세션 영속화(SQLite)

## 2. API

### `GET /health`

- 준비 완료: `{"status":"ok","memory":{...}}`
- 미준비: `{"status":"not_ok","error":"..."}`

### `POST /start`

- request:
  - `session_id`
  - `npc_id` (기본 `saya`)
- response:
  - `session_id`
  - `npc_id`
  - `status=started`

### `POST /turn`

- request:
  - `session_id`
  - `player_action` (`talk|gift|invite_date`)
  - `player_text`
  - `player_name`
  - `player_love`
  - `player_rel`
- response:
  - `saya_narration`, `saya_dialogue`, `emotion`, `image_key`
  - `player_options` (다음 반응 선택지 3개)
  - `action_result`, `date_accepted`, `affection_delta`
  - `translated_dialogue`, `wav_path` (현재 번역/TTS 미연결 상태면 원문/None)

### `POST /session/save`

- Ren'Py 저장 이벤트 시 호출.
- 세션을 `saved=1`로 마킹.

### `POST /session/discard`

- 미저장 세션 폐기용.

## 3. 턴 처리 설계

### 3.1 액션 판정

- `talk`:
  - 현재 규칙 기반 기본 판정(결과코드/호감도 변화량).
- `gift`:
  - **LLM function calling 판정**으로 수용/거절 맥락 및 호감도 변화를 판정.
  - 입력: `player_rel`, `player_love`, `npc_emotion`, `player_text`
  - 출력 스키마:
    - `action_result`
    - `date_accepted` (gift에서는 false)
    - `affection_delta` (정수, -10~15)
- `invite_date`:
  - **LLM function calling 판정**으로 수락/거절 판정.
  - 입력: `player_rel`, `player_love`, `npc_emotion`, `player_text`
  - 출력 스키마:
    - `action_result`
    - `date_accepted` (bool)
    - `affection_delta` (정수, -10~15)

### 3.2 LangGraph 노드

1. `memory`
  - 현재 발화 기준 장기기억 슬롯 검색
  - 최근 턴 요약 결합
2. `generate`
  - 사야 서술+대사 생성
  - 액션 판정 결과와 메모리/FSM 컨텍스트를 프롬프트에 반영
3. `parse`
  - 출력 파싱(서술/대사)
4. `emotion`
  - 감정 라벨 추론
5. `options`
  - 플레이어 반응 선택지 3개 생성

### 3.3 상태 커밋

- 세션 DB 갱신:
  - `turn`, `player_name`, `npc_emotion`, `saved`
- 메모리 DB 갱신:
  - 턴 로그 저장
  - 후보 추출/점수화/승격
  - vec 인덱스 업데이트

## 4. 저장소 설계

### 세션 DB (`DATE_SAYA_SESSION_DB`)

- 기본값:
  - `/home/hosung/pytorch-demo/RomanceArena/date_saya_backend/outputs/sessions.sqlite3`
- 테이블:
  - `sessions(session_id, npc_id, turn, player_name, saved, npc_emotion, updated_at)`

### 메모리 DB (`DATE_SAYA_MEMORY_DB`)

- 기본값:
  - `/home/hosung/pytorch-demo/RomanceArena/date_saya_backend/outputs/memory/memory.sqlite3`
- 테이블:
  - `chat_turns`
  - `memory_candidates`
  - `memory_slots`
  - `memory_slot_vec` (sqlite-vec virtual table)

## 5. 런타임/환경변수

### vLLM / Saya RP 런타임

- `DATE_SAYA_AUTO_START_VLLM` (`1|0`, 기본 `1`)
- `DATE_SAYA_LLM_MODEL_PATH` (기본 `/home/hosung/pytorch-demo/RomanceArena/date_saya_backend/model_assets/saya_rp_4b_v3`)
- `DATE_SAYA_LLM_HOST` (기본 `127.0.0.1`)
- `DATE_SAYA_LLM_PORT` (기본 `8100`)
- `DATE_SAYA_LLM_BASE_URL` (기본 `http://127.0.0.1:8100`)
- `DATE_SAYA_LLM_MODEL_NAME` (기본 `saya-rp-4b`)
- `DATE_SAYA_LLM_MAX_MODEL_LEN` (기본 `1536`)
- `DATE_SAYA_LLM_MAX_NEW_TOKENS` (기본 `220`)
- `DATE_SAYA_LLM_TEMPERATURE` (기본 `0.75`)
- `DATE_SAYA_LLM_GPU_MEMORY_UTILIZATION` (기본 `0.85`)
- `DATE_SAYA_LLM_MAX_NUM_SEQS` (기본 `1`)
- `DATE_SAYA_LLM_TOOL_CALL_PARSER` (기본 `qwen3_xml`)
- `DATE_SAYA_LLM_QUANTIZATION` (기본 `bitsandbytes`)
- `DATE_SAYA_LLM_LOAD_FORMAT` (기본 `bitsandbytes`)
- `DATE_SAYA_LLM_TIMEOUT` (기본 `120`)

### 메모리

- `DATE_SAYA_MEMORY_DB`
- `DATE_SAYA_MEMORY_UPDATE_EVERY` (기본 `1`)
- `DATE_SAYA_MEMORY_RECENT_WINDOW` (기본 `6`)
- `DATE_SAYA_MEMORY_RETRIEVAL_LIMIT` (기본 `8`)
- `DATE_SAYA_MEMORY_PROMOTE_THRESHOLD` (기본 `0.65`)
- `DATE_SAYA_MEMORY_VECTOR_DIM` (기본 `1024`)
- `DATE_SAYA_MEMORY_MAX_SUMMARY_CHARS` (기본 `1200`)

## 6. 실행

프로젝트 루트에서 백엔드만 실행:

```bash
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

Ren'Py와 함께 실행:

```bash
cd /home/hosung/pytorch-demo/RomanceArena/date_saya
./run_with_backend.sh
```

## 7. 운영 원칙

- 핵심 판정(`gift`, `invite_date`)은 vLLM function calling 결과를 사용한다.
- 임의 키워드 기반 보정/문장 치환을 넣지 않는다.
- 출력 형식이 깨지면 오류로 드러내고 원인 수정한다.
