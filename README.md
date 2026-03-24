# RomanceArena

`RomanceArena`는 Ren'Py 프론트엔드와 FastAPI/LangGraph 백엔드를 결합한 LLM 연애 시뮬레이션 프로젝트다.  
현재 메인 타깃은 `date_saya` 시나리오다.

## 핵심 특징

- 액션 중심 턴제 상호작용:
  - `talk`: 대화 진행
  - `gift`: 선물 제시
  - `invite_date`: 데이트 제안
- NPC 반응 생성:
  - 서술 1블록 + 대사 1블록
  - 감정 라벨(`happy|sad|angry|neutral`)과 표정 스프라이트 연동
- 데이트 판정:
  - `invite_date`는 **LLM function-calling**으로 수락/거절 및 호감도 변화량 판정
- 선물 판정:
  - `gift`도 **LLM function-calling**으로 수용/거절 맥락 및 호감도 변화량 판정
  - 입력: 관계 단계, 현재 호감도, NPC 직전 감정, 플레이어 발화
- 장기기억:
  - SQLite + sqlite-vec 기반 메모리 체인
  - 턴 로그 저장 → 후보 추출 → 점수화/승격 → 벡터 검색 → 다음 턴 프롬프트 주입
- 세션 지속성:
  - Ren'Py 저장 시 백엔드 세션을 `saved=1`로 마킹
  - 저장하지 않은 세션은 백엔드 재시작 시 자동 폐기

## 폴더 구조

- `date_saya/`
  - Ren'Py 게임 클라이언트
  - API 브릿지: `game/llm_bridge.rpy`
  - 상호작용 라벨: `game/interact.rpy`
  - 원클릭 실행 스크립트: `run_with_backend.sh`
- `date_saya_backend/`
  - API: `/health`, `/start`, `/turn`, `/session/save`, `/session/discard`
  - 턴 그래프: `pipeline.py`
  - 게임 로직/LLM 호출: `service.py`
  - 장기기억 체인: `memory_chain.py`
  - 세션 저장소: `session_store.py`
  - vLLM 런타임 관리자: `runtime.py`

## 실행

권장(백엔드+Ren'Py 동시 실행):

```bash
cd /home/hosung/pytorch-demo/RomanceArena/date_saya
./run_with_backend.sh
```

수동 실행:

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

```bash
/home/hosung/pytorch-demo/renpy-8.3.0-sdk/renpy.sh /home/hosung/pytorch-demo/RomanceArena/date_saya
```

## 문서

- 설계/메커니즘: [Romance_Arena.md](/home/hosung/pytorch-demo/RomanceArena/Romance_Arena.md)
- 백엔드 상세: [date_saya_backend/README.md](/home/hosung/pytorch-demo/RomanceArena/date_saya_backend/README.md)
