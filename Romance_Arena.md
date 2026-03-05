# LLM Romance Arena
턴제 연애 전략 시뮬레이션 시스템 설계 (구현 반영 버전)

---

## 1. 프로젝트 개요

LLM Romance Arena는 인간 플레이어와 LLM 기반 NPC가 턴 단위로 상호작용하며 관계를 발전시키는 시뮬레이션 시스템이다.  
플레이어는 자유 텍스트 대신 정해진 액션을 선택하고, NPC는 현재 상태/기억/성격을 기반으로 다음 행동을 결정한다.

현재 구현은 `RomanceArena/romance_arena` 패키지에 반영되어 있다.

---

## 2. 현재 구현 범위 (MVP)

1. NPC 2명 시나리오
- 사야 (`saya`)
- 마이 (`mai`)

2. 상태 변수
- `affection`
- `trust`
- `interest`
- `jealousy`
- `mood`
- `relationship_stage`

3. 턴 흐름
- Player Action
- Environment Update
- NPC Action (LLM function-calling + personality policy 결합)
- Environment Update
- Outcome 평가

4. 기억 시스템
- SQLite + sqlite-vec 기반 단기/장기 메모리 저장

5. 실행 인터페이스
- CLI
- FastAPI (`/start`, `/turn`, `/memory/{session_id}`)

---

## 3. 시스템 구조

```text
Player Action
  ↓
RomanceEnvironment (state transition)
  ↓
RomanceNPCAgent
  ├─ LLM function-calling (openai/vllm compat)
  ├─ Personality+State policy re-rank
  └─ Fallback policy (only if LLM path fails)
  ↓
NPC Action + Dialogue
  ↓
RomanceEnvironment update
  ↓
SQLiteMemoryStore update (short/long-term)
  ↓
Outcome check (success/failure/ongoing)
```

---

## 4. Environment

`romance_arena/environment.py`

- 상태 값 범위: `1 ~ 100` 클램프
- `action`은 선택만 담당
- 상태 증감은 LLM이 `delta_affection/trust/interest/jealousy/mood`로 제안
- `delta_*` 범위: `-10 ~ 10` 검증
- `relationship_stage`는 상태 임계치로 자동 계산

관계 단계:
- `stranger`
- `acquaintance`
- `friend`
- `romantic_interest`
- `dating`
- `relationship`

---

## 5. Action Space

### 5.1 Player Action Space

- `talk`
- `compliment`
- `gift`
- `invite_date`
- `apologize`
- `joke`
- `tease`
- `ignore`

### 5.2 NPC Action Space

- `talk`
- `compliment`
- `tease`
- `apologize`
- `ignore`
- `change_topic`
- `invite_date`

NPC별 허용 행동 목록은 `npc_configs.py`에서 관리한다.

---

## 6. NPC Agent

`romance_arena/agent.py`

### 6.1 LLM Function-Calling

- OpenAI/vLLM 호환 `chat/completions` API 사용
- tool schema: `choose_npc_action`
- required fields:
  - `action`
  - `reason`
  - `dialogue`
- schema 검증 + NPC 허용 action 검증 후만 반영
- LLM action 결과는 성격/상태 정책으로 2차 보정(re-rank) 후 최종 반영
- `dialogue`가 짧거나 품질이 낮으면 LLM 대사를 추가 생성해 교체

상태 전이용 별도 tool schema:
- `choose_state_delta`
- required fields:
  - `delta_affection`
  - `delta_trust`
  - `delta_interest`
  - `delta_jealousy`
  - `delta_mood`
  - `reason`

환경변수:
- `ROMANCE_LLM_MODE=openai_compat`
- `ROMANCE_LLM_BASE_URL=http://127.0.0.1:8000/v1`
- `ROMANCE_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct`
- `ROMANCE_LLM_API_KEY` (optional)
- `ROMANCE_LLM_RETRIES` (default 2)

### 6.2 Personality Policy (LLM 공통 적용)

성격 가중치 정책은 fallback 전용이 아니라 LLM 경로에도 공통 적용:
- `kind` (사야)
- `tsundere` (마이)

상태/이벤트(예: trust 저하, jealousy 증가, first_argument) 기반으로 행동 가중치를 동적으로 조정한다.

### 6.3 Fallback 사용 조건

아래 경우에만 fallback 사용:
- function-calling 실패
- schema 검증 실패
- 허용 action 위반
- LLM 응답 타임아웃/재시도 실패

---

## 7. Memory System

`romance_arena/memory_store.py`

SQLite 파일:
- `outputs/romance_memory.sqlite3`

테이블:
1. `short_term_memory`
- 턴별 행동/이벤트/상태 스냅샷 저장

2. `long_term_memory`
- LLM function-calling 기반 장기기억 승격 저장
- `extract_long_term_memory` tool schema로 `memory_key/note/score` 추출
- 세션 시작 시 `first_meeting` 시드는 기본 등록

3. `long_term_vec` (sqlite-vec 가상 테이블)
- `long_term_memory.note`를 벡터화해 저장
- retrieval 시 의미 유사도 검색에 사용

검색 우선순위:
1) sqlite-vec 의미 검색  
2) 실패 시 lexical fallback

엔진(`engine.py`)에서 턴 종료 시 자동 저장/승격한다.

---

## 8. Outcome 규칙

성공 조건:
- `affection > 85`
- `trust > 70`
- `relationship_stage == relationship`

실패 조건:
- `trust < 10` 또는 `jealousy > 80`

그 외:
- `ongoing`

---

## 9. 구현 파일 구조

```text
romance_arena/
  __init__.py
  models.py
  npc/
    agent.py
    configs.py
    llm_client.py
    schemas.py
  player/
    generator.py
    renderer.py
  environment/
    core.py
  memory_store.py
  engine.py
  api.py
  cli.py
```

---

## 10. 실행 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

CLI:

```bash
python -m romance_arena.cli
```

API:

```bash
uvicorn romance_arena.api:app --host 0.0.0.0 --port 8000
```

주요 API:
- `GET /npcs`
- `POST /start`
- `POST /turn`
- `GET /memory/{session_id}`

---

## 11. PokeLLMon 참조 범위

PokeLLMon은 다음 개념을 참고했다.
- 턴제 에이전트 루프
- 상태 기반 의사결정
- 행동 선택 인터페이스 구조

전투 도메인 로직(배틀 규칙/데미지 계산)은 사용하지 않고,  
연애 도메인 상태 전이와 기억 시스템은 본 프로젝트에서 독립 구현했다.
