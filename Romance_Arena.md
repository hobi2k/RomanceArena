# Romance Arena 설계 문서 (현재 적용판)

이 문서는 현재 코드 기준으로 `date_saya` + `date_saya_backend` 아키텍처를 설명한다.

---

## 1. 목표

- Ren'Py 비주얼 노벨 템플릿을 LLM 기반 상호작용 게임으로 전환
- 사야 NPC의 반응을 실시간 생성
- 반응 감정에 따라 스프라이트를 전환
- 플레이어 선택지 또한 LLM이 생성
- 메모리는 SQLite(+sqlite-vec)로 누적

---

## 2. 시스템 구조

### 2.1 Client (Ren'Py)

- 경로: `date_saya/game`
- 역할:
  - UI/연출/라벨 진행
  - API 호출 브릿지(`llm_bridge.rpy`)
  - 사야 표정 이미지 표시(`neutral_saya`, `smile_saya`, `crying_saya`, `annoyed_saya`)
  - `wav_path` 수신 시 음성 재생

### 2.2 Backend (FastAPI + LangGraph)

- 경로: `date_saya_backend`
- 역할:
  - `/start`, `/turn`, `/health` 제공
  - 턴 그래프 실행
  - 세션별 메모리 저장/조회
  - LLM/감정/선택지 생성
  - 번역/TTS(옵션) 연계

### 2.3 TTS Runtime

- 경로: `date_saya_backend/sbv_runtime`
- ONNX 기반 런타임
- 백엔드 영역으로 이동 완료(클라이언트 분리)

---

## 3. 턴 파이프라인 (LangGraph)

1. `context`: 최근 대화 메모리 로드  
2. `saya`: 사야 서술+대사 생성  
3. `emotion`: 감정 라벨 추론(`neutral|happy|sad|angry`)  
4. `player_options`: 플레이어 선택지 3개 생성  
5. `translate_tts`: 번역/TTS 옵션 호출  
6. `commit`: 턴 로그 저장

---

## 4. 메모리

- DB: `DATE_SAYA_MEMORY_DB` (기본 `date_saya/outputs/date_saya_memory.sqlite3`)
- 테이블:
  - `turns`: 세션 턴 로그 저장
  - `turn_vec`: sqlite-vec 가상 테이블(확장 로드 가능 시)
- 기본 검색은 최근 턴 문맥 사용, vec는 확장 가능 포인트

---

## 5. LLM 연동

- OpenAI-compatible API 사용 (`/v1/chat/completions`)
- 기본 대상:
  - `DATE_SAYA_LLM_BASE_URL=http://127.0.0.1:8100/v1`
  - `DATE_SAYA_LLM_MODEL=saya-rp-4b`
- LLM 호출 실패 시:
  - 백엔드는 500을 내지 않고 폴백 텍스트/폴백 선택지 반환
  - Ren'Py 진행이 멈추지 않도록 보장

---

## 6. 자동 실행 전략

`date_saya/run_with_backend.sh`가 다음을 처리한다.

1. (옵션) vLLM 서버 자동 기동  
2. FastAPI 백엔드 기동  
3. 헬스체크 통과 후 Ren'Py 실행  
4. 종료 시 하위 프로세스 정리

이 방식은 Gradio mount와 달리 프로세스는 분리하지만 사용자 입장에선 "한 번에 실행"된다.

---

## 7. API 스키마 요약

- `POST /start`
  - 입력: `session_id`, `npc_id`
  - 출력: 세션 시작 상태
- `POST /turn`
  - 입력: `session_id`, `player_action`, `player_text`
  - 출력:
    - `saya_narration`, `saya_dialogue`, `emotion`, `image_key`
    - `player_options`
    - `translated_dialogue`, `wav_path`

---

## 8. 구현 범위 메모

- 현재는 사야 1인 중심 시나리오
- 플레이어 선택지는 모델이 생성하되, Ren'Py 라벨 분기는 점진적으로 확장 예정
- `romance_arena/`의 기존 전략 배틀 실험 코드는 별도 레거시 참고 대상으로 유지
