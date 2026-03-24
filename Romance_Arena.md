# Romance Arena 설계 문서 (현재 구현 기준)

이 문서는 `date_saya`(Ren'Py) + `date_saya_backend`(FastAPI/LangGraph) 기준의 현재 구조와 게임 메커니즘을 정의한다.

## 1. 설계 목표

- 단순 대화봇이 아닌 **액션 기반 연애 시뮬레이션** 구현.
- 플레이어 액션(`talk`, `gift`, `invite_date`)마다 다른 판정과 서사 결과를 제공.
- NPC 감정 상태를 턴 간 유지하고, 그 상태를 다음 판정에 반영.
- 장기기억을 vec로 저장/검색하여 대화 일관성을 유지.
- Ren'Py 저장/불러오기와 백엔드 세션 지속성을 일치시킴.

## 2. 아키텍처

### 2.1 Ren'Py 클라이언트 (`date_saya`)

- UI, 씬 전환, 라벨 흐름 담당.
- `game/llm_bridge.rpy`에서 백엔드 API 호출.
- 턴 결과(`emotion`)를 스프라이트(`neutral/smile/crying/annoyed`)에 반영.
- `player_options`를 메뉴로 표시하고 선택지를 다음 턴 입력으로 사용.
- 저장 시 `/session/save`, 미저장 새 게임 시작 시 `/session/discard` 연동.

### 2.2 백엔드 (`date_saya_backend`)

- FastAPI 엔드포인트 제공:
  - `GET /health`
  - `POST /start`
  - `POST /turn`
  - `POST /session/save`
  - `POST /session/discard`
- `runtime.py`에서 vLLM OpenAI 서버 자동 기동/중지 관리.
- `service.py`에서 액션 판정, LLM 호출, 세션/메모리 갱신 수행.
- `pipeline.py`에서 LangGraph 턴 파이프라인 실행.

### 2.3 데이터 저장소

- 세션 DB: `outputs/sessions.sqlite3`
  - `sessions(session_id, npc_id, turn, player_name, saved, npc_emotion, updated_at)`
- 메모리 DB: `outputs/memory/memory.sqlite3`
  - `chat_turns`: 턴 원문 로그
  - `memory_candidates`: 후보 기억
  - `memory_slots`: 승격된 장기기억
  - `memory_slot_vec`: sqlite-vec 임베딩 인덱스

## 3. 게임 메커니즘

### 3.1 액션 타입

- `talk`: 대화 진행. 기본적으로 관계 진전에 유리한 변화량.
- `gift`: **LLM function-calling 판정**으로 수용/거절 맥락과 변화량을 결정.
- `invite_date`: **LLM function-calling 판정**으로 수락/거절을 결정.

### 3.2 선물/데이트 판정 설계

- `gift`, `invite_date`는 규칙 하드코딩이 아닌 툴 스키마 호출로 판정.
- 판정 입력:
  - `player_rel` (관계 단계)
  - `player_love` (현재 호감도)
  - `npc_emotion` (직전 턴 감정)
  - `player_text` (제안 문장)
- 판정 출력:
  - `action_result`
  - `date_accepted` (bool)
  - `affection_delta` (정수, -10~15)
- 결과는 Ren'Py에 전달되어:
  - `date_accepted=True`면 `dateA` 진입
  - `affection_delta`만큼 `Alove` 반영

### 3.3 NPC 감정 상태

- 매 턴 `saya_narration + saya_dialogue`로 감정 추론(`happy|sad|angry|neutral`).
- 추론 결과를 세션 DB의 `npc_emotion`에 저장.
- 다음 턴 판정(특히 `invite_date`) 입력으로 재사용.

## 4. 턴 파이프라인 (LangGraph)

`pipeline.py`의 실행 순서:

1. `memory`: 현재 발화 기준 vec 장기기억 검색 + 최근 턴 요약 구성
2. `generate`: 사야 서술/대사 생성 (메모리 + 액션 판정 결과 포함)
3. `parse`: 서술/대사 분리
4. `emotion`: 감정 판정
5. `options`: 다음 플레이어 선택지 3개 생성

`service.py`에서 그래프 실행 전 액션 판정을 수행하고, 그래프 실행 후 메모리 업데이트를 커밋한다.

## 5. 장기기억 체인

`memory_chain.py`는 다음 순서로 동작:

1. 턴 저장:
  - `chat_turns`에 user/assistant 턴 쌍 기록
2. 후보 추출:
  - LLM JSON 추출(`type, subject, key, value, confidence, future_impact, emotion_intensity`)
3. 점수화/승격:
  - recurrence/novelty 포함 합성 점수 계산
  - 임계값 이상은 `memory_slots`로 승격
4. vec 인덱싱:
  - HashingVectorizer 임베딩을 `memory_slot_vec`에 저장
5. 검색 주입:
  - 현재 발화 임베딩으로 유사 슬롯 검색 후 system prompt에 삽입

## 6. 세션/저장 정책

- `start`:
  - 새 세션 생성(`saved=False`)
- Ren'Py 저장:
  - `/session/save` 호출로 세션 `saved=True`
- Ren'Py 새 게임:
  - 기존 미저장 세션이면 `/session/discard`
- 백엔드 시작 시:
  - `saved=False` 세션 일괄 삭제
- Ren'Py 로드:
  - 저장된 `session_id`로 이어서 진행

## 7. 오류 처리 원칙

- LLM 핵심 단계(JSON 파싱, tool call)는 실패 시 즉시 오류를 반환한다.
- 임의 키워드 기반 후처리/강제 치환은 사용하지 않는다.
- 비정상 출력은 숨기지 않고 원인 파악 가능하게 유지한다.

## 8. 향후 확장 포인트

- `talk`도 function-calling 판정으로 승격.
- 다중 NPC(예: 사야/마이) 세션 분리 확장.
- TTS/번역 파이프라인 재연결 시 `wav_path` 실사용.
