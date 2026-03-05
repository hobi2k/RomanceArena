# Romance Arena

`Romance_Arena.md` 기반 MVP 구현.

## 포함 기능

- 2개 NPC 시나리오 (`saya`, `mai`)
- 공통 상태 관리
  - `affection`, `trust`, `interest`, `jealousy`, `mood`, `relationship_stage`
- 턴 구조
  - Player Action -> Environment Update -> NPC Action -> Environment Update
- 상태 전이
  - `action`은 선택만 담당
  - 상태 변화량은 LLM function-calling의 `delta_*`로 결정 (`-10~10`)
  - 안전장치로 범위 검증 + 상태값 `1~100` 클램프
- JSON schema + function-calling
  - `choose_npc_action` tool schema
  - OpenAI/vLLM 호환 API 호출(`ROMANCE_LLM_MODE=openai_compat`)
  - payload validation + 허용 action 검증
- NPC 성격 기반 행동 전략
  - personality(`kind` for saya, `tsundere` for mai)별 가중치 정책
  - 상태/이벤트 기반 동적 bias 적용
  - LLM 경로에서도 정책 가중치로 action 보정(리랭크)
- 대사 생성 품질 강화
  - 기본: LLM function-calling 결과의 `dialogue` 사용
  - 짧거나 품질이 낮은 경우 LLM으로 대사 재생성
  - 최종 실패 시에만 템플릿 대사 fallback
- SQLite 메모리 시스템
  - 단기 기억: 최근 턴 로그(`short_term_memory`)
  - 장기 기억: LLM function-calling 기반 승격(`long_term_memory`)
  - 벡터 인덱스: `sqlite-vec` 기반 `long_term_vec`
  - 기본 DB: `outputs/romance_memory.sqlite3`
- API/FastAPI + CLI

## 코드 구조

- `romance_arena/player/`: 플레이어 턴 텍스트 생성/렌더링
- `romance_arena/npc/`: NPC 프로필, 에이전트, LLM 호출, function-calling schema
- `romance_arena/environment/`: 상태 전이 및 결과 판정

## 실행

```bash
cd RomanceArena
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

LLM function-calling 사용(vLLM/OpenAI 호환):

```bash
export ROMANCE_LLM_MODE=openai_compat
export ROMANCE_LLM_BASE_URL=http://127.0.0.1:8000/v1
export ROMANCE_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
export ROMANCE_LLM_RETRIES=2
```

또는 `.env` 파일 사용 (자동 로드):

```dotenv
ROMANCE_LLM_MODE=openai_compat
ROMANCE_LLM_BASE_URL=http://127.0.0.1:8000/v1
ROMANCE_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
ROMANCE_LLM_API_KEY=
ROMANCE_LLM_RETRIES=2
ROMANCE_LLM_TIMEOUT=30
```

주요 엔드포인트:

- `GET /npcs`
- `POST /start`
- `POST /turn`
- `GET /memory/{session_id}`

## 설계 메모

- PokeLLMon은 에이전트 루프/의사결정 구조 참고 대상으로 보고, 전투 규칙 엔진은 가져오지 않음.
- Romance domain 상태 전이/단계 규칙은 이 프로젝트에서 독립 구현.
- 메모리 retrieval은 `sqlite-vec` 우선, 실패 시 lexical fallback으로 동작.
