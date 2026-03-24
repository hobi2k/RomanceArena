from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import json
import re
import sqlite3

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
import sqlite_vec


def _utc_now() -> str:
    """UTC 현재 시간을 ISO-8601 문자열로 반환한다.

    Args:
        없음.

    Returns:
        str: UTC ISO-8601 타임스탬프.
    """
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    """값을 float으로 안전 변환한다.

    Args:
        v: 변환할 값.
        default: 실패 시 반환값.

    Returns:
        float: 변환 결과 또는 기본값.
    """
    try:
        return float(v)
    except Exception:
        return default


@dataclass
class SummaryMemoryConfig:
    """장기기억 체인 설정값.

    Args:
        db_path: SQLite 파일 경로.
        update_every_turns: N턴마다 후보 추출/승격 수행.
        recent_turn_window: 최근 N턴 스냅샷 길이.
        retrieval_limit: 검색 슬롯 최대 개수.
        promote_threshold: 후보 승격 점수 임계치.
        vector_dim: sqlite-vec 임베딩 차원.
        max_summary_chars: 주입 컨텍스트 최대 길이.

    Returns:
        SummaryMemoryConfig: 설정 객체.
    """

    db_path: str
    update_every_turns: int = 1
    recent_turn_window: int = 6
    retrieval_limit: int = 8
    promote_threshold: float = 0.65
    vector_dim: int = 1024
    max_summary_chars: int = 1200


class SummaryMemoryChain:
    """SQLite + sqlite-vec 기반 장기기억 체인.

    Args:
        llm_chat: LLM 채팅 호출 함수.
        config: 메모리 체인 설정.

    Returns:
        SummaryMemoryChain: 메모리 체인 인스턴스.
    """

    def __init__(self, *, llm_chat: Callable[..., str], config: SummaryMemoryConfig) -> None:
        self.llm_chat = llm_chat
        self.config = config
        self.db_path = Path(config.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.vectorizer = HashingVectorizer(
            n_features=int(self.config.vector_dim),
            alternate_sign=False,
            norm=None,
            ngram_range=(1, 2),
        )
        self._init_db()
        self._init_vec_table()

    def _init_db(self) -> None:
        """기본 테이블과 인덱스를 초기화한다.

        Args:
            없음.

        Returns:
            None.
        """
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_idx INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_idx INTEGER NOT NULL,
                type TEXT NOT NULL,
                subject TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                evidence TEXT NOT NULL,
                confidence REAL NOT NULL,
                future_impact REAL NOT NULL,
                emotion_intensity REAL NOT NULL,
                recurrence REAL NOT NULL,
                novelty REAL NOT NULL,
                score REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                subject TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                score REAL NOT NULL,
                last_evidence_turn INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_id, key)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_turns_session_turn ON chat_turns(session_id, turn_idx)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_slot_session_score ON memory_slots(session_id, score DESC)"
        )
        self.conn.commit()

    def _init_vec_table(self) -> None:
        """sqlite-vec 가상 테이블을 생성한다.

        Args:
            없음.

        Returns:
            None.
        """
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_slot_vec
            USING vec0(embedding float[{int(self.config.vector_dim)}])
            """
        )
        self.conn.commit()

    def _embed_text(self, text: str) -> bytes:
        """텍스트를 임베딩 blob으로 변환한다.

        Args:
            text: 임베딩할 텍스트.

        Returns:
            bytes: sqlite-vec 검색 가능한 float32 blob.
        """
        vec = self.vectorizer.transform([text]).toarray()[0].astype("float32")
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return sqlite_vec.serialize_float32(vec.tolist())

    def _next_turn_idx(self, session_id: str) -> int:
        """세션의 다음 turn index를 계산한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            int: 다음 턴 인덱스.
        """
        row = self.conn.execute(
            "SELECT COALESCE(MAX(turn_idx), 0) AS max_turn FROM chat_turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["max_turn"]) + 1

    def _insert_turn_pair(self, session_id: str, turn_idx: int, user_text: str, assistant_text: str) -> None:
        """턴 쌍(user/assistant)을 저장한다.

        Args:
            session_id: 세션 식별자.
            turn_idx: 턴 인덱스.
            user_text: 플레이어 텍스트.
            assistant_text: 사야 텍스트.

        Returns:
            None.
        """
        now = _utc_now()
        self.conn.executemany(
            """
            INSERT INTO chat_turns(session_id, turn_idx, role, text, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (session_id, turn_idx, "user", user_text.strip(), now),
                (session_id, turn_idx, "assistant", assistant_text.strip(), now),
            ],
        )
        self.conn.commit()

    def _extract_candidates(self, user_text: str, assistant_text: str) -> list[dict[str, Any]]:
        """LLM으로 장기기억 후보를 추출한다.

        Args:
            user_text: 플레이어 입력.
            assistant_text: 사야 출력.

        Returns:
            list[dict[str, Any]]: 정제된 후보 목록.
        """
        raw = self.llm_chat(
            system_prompt="""
                너는 대화 장기기억 추출기다.
                반드시 JSON 객체 하나만 출력한다.
                스키마:
                {
                  "candidates": [
                    {
                      "type": "preference|fact|promise|relationship|emotion|plan|boundary",
                      "subject": "user|assistant|pair",
                      "key": "짧은_식별자",
                      "value": "핵심 내용",
                      "confidence": 0.0,
                      "future_impact": 0.0,
                      "emotion_intensity": 0.0
                    }
                  ]
                }
                규칙:
                - 장기 대화에 영향 없는 잡담은 제외.
                - confidence/future_impact/emotion_intensity는 0~1.
                - JSON 외 텍스트 금지.
            """,
            user_prompt=f"""
                [user]
                {user_text.strip()}

                [assistant]
                {assistant_text.strip()}
            """,
            max_tokens=360,
            temperature=0.2,
        )
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise RuntimeError(f"memory candidate json parse failed: {raw}")
        data = json.loads(m.group(0))
        arr = data.get("candidates")
        if not isinstance(arr, list):
            raise RuntimeError(f"memory candidates payload invalid: {data}")

        out: list[dict[str, Any]] = []
        for c in arr:
            if not isinstance(c, dict):
                continue
            t = str(c.get("type", "")).strip()
            s = str(c.get("subject", "")).strip()
            k = str(c.get("key", "")).strip()
            v = str(c.get("value", "")).strip()
            if not (t and s and k and v):
                continue
            out.append(
                {
                    "type": t[:40],
                    "subject": s[:24],
                    "key": k[:120],
                    "value": v[:400],
                    "confidence": min(1.0, max(0.0, _safe_float(c.get("confidence"), 0.0))),
                    "future_impact": min(1.0, max(0.0, _safe_float(c.get("future_impact"), 0.0))),
                    "emotion_intensity": min(1.0, max(0.0, _safe_float(c.get("emotion_intensity"), 0.0))),
                }
            )
        return out

    def _type_importance(self, memory_type: str) -> float:
        """메모리 타입별 가중치를 반환한다.

        Args:
            memory_type: 후보 메모리 타입.

        Returns:
            float: 타입 중요도.
        """
        mapping = {
            "promise": 1.0,
            "boundary": 0.95,
            "fact": 0.85,
            "relationship": 0.80,
            "plan": 0.75,
            "preference": 0.65,
            "emotion": 0.55,
        }
        return mapping.get(memory_type, 0.5)

    def _compute_recurrence(self, session_id: str, key: str) -> float:
        """동일 key 재등장 빈도로 recurrence 점수를 계산한다.

        Args:
            session_id: 세션 식별자.
            key: 메모리 key.

        Returns:
            float: 0~1 recurrence 점수.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM memory_candidates WHERE session_id = ? AND key = ?",
            (session_id, key),
        ).fetchone()
        cnt = int(row["cnt"]) if row else 0
        return min(1.0, cnt / 3.0)

    def _compute_novelty(self, session_id: str, key: str, value: str) -> float:
        """기존 슬롯 대비 novelty를 계산한다.

        Args:
            session_id: 세션 식별자.
            key: 메모리 key.
            value: 메모리 value.

        Returns:
            float: 0~1 novelty 점수.
        """
        row = self.conn.execute(
            "SELECT value FROM memory_slots WHERE session_id = ? AND key = ?",
            (session_id, key),
        ).fetchone()
        if row is None:
            return 1.0
        old = str(row["value"])
        if old == value:
            return 0.0
        return 0.4

    def _score_candidate(
        self,
        *,
        memory_type: str,
        confidence: float,
        future_impact: float,
        emotion_intensity: float,
        recurrence: float,
        novelty: float,
    ) -> float:
        """후보를 합성 점수로 계산한다.

        Args:
            memory_type: 메모리 타입.
            confidence: 신뢰도.
            future_impact: 미래 영향도.
            emotion_intensity: 감정 강도.
            recurrence: 재등장 점수.
            novelty: 새로움 점수.

        Returns:
            float: 0~1 최종 점수.
        """
        score = (
            0.30 * self._type_importance(memory_type)
            + 0.20 * confidence
            + 0.20 * future_impact
            + 0.15 * emotion_intensity
            + 0.10 * recurrence
            + 0.05 * novelty
        )
        return min(1.0, max(0.0, score))

    def _upsert_slot_vector(self, slot_id: int, text: str) -> None:
        """슬롯 벡터를 rowid=slot_id로 갱신한다.

        Args:
            slot_id: memory_slots id.
            text: 임베딩 텍스트.

        Returns:
            None.
        """
        blob = self._embed_text(text)
        self.conn.execute("DELETE FROM memory_slot_vec WHERE rowid = ?", (slot_id,))
        self.conn.execute(
            "INSERT INTO memory_slot_vec(rowid, embedding) VALUES (?, ?)",
            (slot_id, blob),
        )

    def _store_candidate_and_promote(
        self,
        *,
        session_id: str,
        turn_idx: int,
        user_text: str,
        assistant_text: str,
        candidate: dict[str, Any],
    ) -> None:
        """후보를 저장하고 점수 임계치 이상은 슬롯으로 승격한다.

        Args:
            session_id: 세션 식별자.
            turn_idx: 턴 인덱스.
            user_text: 플레이어 텍스트.
            assistant_text: 사야 텍스트.
            candidate: 후보 객체.

        Returns:
            None.
        """
        recurrence = self._compute_recurrence(session_id, candidate["key"])
        novelty = self._compute_novelty(session_id, candidate["key"], candidate["value"])
        score = self._score_candidate(
            memory_type=candidate["type"],
            confidence=candidate["confidence"],
            future_impact=candidate["future_impact"],
            emotion_intensity=candidate["emotion_intensity"],
            recurrence=recurrence,
            novelty=novelty,
        )
        status = "promoted" if score >= self.config.promote_threshold else "candidate"
        evidence = f"user: {user_text.strip()}\nassistant: {assistant_text.strip()}"[:1200]
        self.conn.execute(
            """
            INSERT INTO memory_candidates(
                session_id, turn_idx, type, subject, key, value, evidence,
                confidence, future_impact, emotion_intensity, recurrence, novelty,
                score, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                turn_idx,
                candidate["type"],
                candidate["subject"],
                candidate["key"],
                candidate["value"],
                evidence,
                candidate["confidence"],
                candidate["future_impact"],
                candidate["emotion_intensity"],
                recurrence,
                novelty,
                score,
                status,
                _utc_now(),
            ),
        )
        if status == "promoted":
            self.conn.execute(
                """
                INSERT INTO memory_slots(session_id, type, subject, key, value, score, last_evidence_turn, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, key)
                DO UPDATE SET
                    type = excluded.type,
                    subject = excluded.subject,
                    value = excluded.value,
                    score = excluded.score,
                    last_evidence_turn = excluded.last_evidence_turn,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    candidate["type"],
                    candidate["subject"],
                    candidate["key"],
                    candidate["value"],
                    score,
                    turn_idx,
                    _utc_now(),
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM memory_slots WHERE session_id = ? AND key = ?",
                (session_id, candidate["key"]),
            ).fetchone()
            if row is not None:
                slot_text = (
                    f"{candidate['key']} {candidate['value']} {candidate['type']} {candidate['subject']}"
                )
                self._upsert_slot_vector(int(row["id"]), slot_text)
        self.conn.commit()

    def _recent_turn_digest(self, session_id: str) -> str:
        """최근 N턴 스냅샷 문자열을 만든다.

        Args:
            session_id: 세션 식별자.

        Returns:
            str: 스냅샷 문자열.
        """
        n = max(1, int(self.config.recent_turn_window))
        rows = self.conn.execute(
            """
            SELECT turn_idx, role, text
            FROM chat_turns
            WHERE session_id = ?
            ORDER BY turn_idx DESC, id DESC
            LIMIT ?
            """,
            (session_id, n * 2),
        ).fetchall()
        if not rows:
            return ""
        lines: list[str] = []
        for r in reversed(rows):
            role = "user" if r["role"] == "user" else "assistant"
            lines.append(f"- ({r['turn_idx']}) {role}: {str(r['text'])[:220]}")
        return "\n".join(lines)

    def _retrieve_slots_vec(self, session_id: str, current_user_text: str) -> list[sqlite3.Row]:
        """sqlite-vec로 장기기억 슬롯을 검색한다.

        Args:
            session_id: 세션 식별자.
            current_user_text: 현재 플레이어 발화.

        Returns:
            list[sqlite3.Row]: 유사도 정렬된 슬롯들.
        """
        q_blob = self._embed_text(current_user_text)
        rows = self.conn.execute(
            """
            SELECT
                s.id,
                s.key,
                s.value,
                s.type,
                s.subject,
                s.score,
                s.last_evidence_turn,
                s.updated_at,
                mv.distance AS vec_distance
            FROM memory_slots s
            JOIN (
                SELECT rowid, distance
                FROM memory_slot_vec
                WHERE embedding MATCH ?
                AND k = ?
            ) mv ON mv.rowid = s.id
            WHERE s.session_id = ?
            ORDER BY mv.distance ASC, s.updated_at DESC
            """,
            (q_blob, max(1, int(self.config.retrieval_limit)), session_id),
        ).fetchall()
        ranked: list[tuple[float, sqlite3.Row]] = []
        for r in rows:
            dist = _safe_float(r["vec_distance"], 1.0)
            sim = max(0.0, 1.0 - dist)
            final_score = float(r["score"]) * 0.35 + sim * 0.65
            ranked.append((final_score, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in ranked[: max(1, int(self.config.retrieval_limit))]]

    def build_memory_context(self, session_id: str, current_user_text: str) -> str:
        """메모리 주입용 컨텍스트 문자열을 생성한다.

        Args:
            session_id: 세션 식별자.
            current_user_text: 현재 플레이어 발화.

        Returns:
            str: system prompt에 넣을 메모리 컨텍스트.
        """
        slots = self._retrieve_slots_vec(session_id, current_user_text) if current_user_text.strip() else []
        digest = self._recent_turn_digest(session_id)
        if not slots and not digest:
            return ""
        lines: list[str] = []
        if slots:
            lines.append("장기기억 슬롯(관련도 높은 순):")
            for s in slots:
                lines.append(
                    f"- [{s['type']}/{s['subject']}] {s['key']} = {s['value']} "
                    f"(score={float(s['score']):.2f}, turn={s['last_evidence_turn']})"
                )
        if digest:
            lines.append("")
            lines.append("최근 대화 스냅샷:")
            lines.append(digest)
        content = (
            "메모리 컨텍스트:\n"
            + "\n".join(lines)
            + "\n\n규칙: 메모리는 참고용이며, 마지막 user 입력에 직접 반응한다."
        )
        if len(content) > int(self.config.max_summary_chars):
            content = content[: int(self.config.max_summary_chars)].rstrip()
        return content

    def update(self, session_id: str, user_text: str, assistant_text: str) -> None:
        """턴 종료 후 메모리 체인을 업데이트한다.

        Args:
            session_id: 세션 식별자.
            user_text: 플레이어 텍스트.
            assistant_text: 사야 텍스트.

        Returns:
            None.
        """
        turn_idx = self._next_turn_idx(session_id)
        self._insert_turn_pair(session_id, turn_idx, user_text, assistant_text)
        if turn_idx % max(1, int(self.config.update_every_turns)) != 0:
            return
        candidates = self._extract_candidates(user_text, assistant_text)
        for c in candidates:
            self._store_candidate_and_promote(
                session_id=session_id,
                turn_idx=turn_idx,
                user_text=user_text,
                assistant_text=assistant_text,
                candidate=c,
            )

    def status(self) -> dict[str, Any]:
        """메모리 체인 런타임 상태를 반환한다.

        Args:
            없음.

        Returns:
            dict[str, Any]: vec 설정/DB 경로/차원 정보.
        """
        return {
            "db_path": str(self.db_path),
            "vector_dim": int(self.config.vector_dim),
            "retrieval_limit": int(self.config.retrieval_limit),
            "promote_threshold": float(self.config.promote_threshold),
        }
