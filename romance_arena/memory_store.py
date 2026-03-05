from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

try:
    import sqlite_vec  # type: ignore
except Exception:
    sqlite_vec = None


class SQLiteMemoryStore:
    """SQLite 기반 메모리 저장소.

    기본 동작:
    - short/long term memory 저장
    - long term memory 목록 조회

    확장 동작(sqlite-vec 사용 가능 시):
    - long term memory note를 벡터화해 `long_term_vec` 인덱스에 저장
    - 의미 유사도 기반 retrieval 우선 사용
    """

    VECTOR_DIM = 32

    def __init__(self, db_path: str | None = None) -> None:
        """SQLite 연결과 기본 스키마/벡터 인덱스를 초기화한다."""
        if db_path is None:
            root = Path(__file__).resolve().parents[1]
            db_path = str(root / "outputs" / "romance_memory.sqlite3")
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.vec_enabled = False
        self._init_schema()
        self._init_vector_extension()

    def _init_schema(self) -> None:
        """short/long-term 메모리 테이블 및 인덱스를 생성한다."""
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS short_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn INTEGER NOT NULL,
                player_action TEXT NOT NULL,
                npc_action TEXT NOT NULL,
                events_json TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                note TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 1,
                first_turn INTEGER NOT NULL,
                last_turn INTEGER NOT NULL,
                occurrence INTEGER NOT NULL DEFAULT 1,
                UNIQUE(session_id, memory_key)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_short_term_session_turn ON short_term_memory(session_id, turn DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_long_term_session_key ON long_term_memory(session_id, memory_key)"
        )
        self.conn.commit()

    def _init_vector_extension(self) -> None:
        """sqlite-vec 확장 로드 및 벡터 테이블 생성.

        실패해도 본문 기능은 유지하며 lexical 검색으로 fallback한다.
        """
        if sqlite_vec is None:
            self.vec_enabled = False
            return

        try:
            sqlite_vec.load(self.conn)
            self.conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS long_term_vec
                USING vec0(embedding float[{self.VECTOR_DIM}])
                """
            )
            self.vec_enabled = True
            self.conn.commit()
        except Exception:
            self.vec_enabled = False

    def save_turn(
        self,
        *,
        session_id: str,
        turn: int,
        player_action: str,
        npc_action: str,
        events: list[str],
        state: dict[str, Any],
    ) -> None:
        """1턴 로그를 short_term_memory에 저장한다."""
        self.conn.execute(
            """
            INSERT INTO short_term_memory(session_id, turn, player_action, npc_action, events_json, state_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                turn,
                player_action,
                npc_action,
                json.dumps(events, ensure_ascii=False),
                json.dumps(state, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def get_recent_events(self, session_id: str, limit: int = 5) -> list[str]:
        """최근 턴 이벤트 태그를 평탄화해서 반환한다."""
        rows = self.conn.execute(
            """
            SELECT events_json FROM short_term_memory
            WHERE session_id = ?
            ORDER BY turn DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        out: list[str] = []
        for row in rows:
            try:
                evs = json.loads(row["events_json"])
            except Exception:
                continue
            if isinstance(evs, list):
                for ev in evs:
                    if isinstance(ev, str):
                        out.append(ev)
        return out

    def upsert_long_term(
        self,
        *,
        session_id: str,
        memory_key: str,
        note: str,
        turn: int,
        score: int = 1,
    ) -> None:
        """장기기억을 upsert하고 벡터 인덱스를 동기화한다.

        - 신규 key: INSERT
        - 기존 key: score/occurrence 누적 UPDATE
        """
        row = self.conn.execute(
            """
            SELECT id, occurrence, score FROM long_term_memory
            WHERE session_id = ? AND memory_key = ?
            """,
            (session_id, memory_key),
        ).fetchone()
        if row is None:
            cur = self.conn.execute(
                """
                INSERT INTO long_term_memory(session_id, memory_key, note, score, first_turn, last_turn, occurrence)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (session_id, memory_key, note, score, turn, turn),
            )
            row_id = int(cur.lastrowid)
        else:
            self.conn.execute(
                """
                UPDATE long_term_memory
                SET note = ?, score = score + ?, last_turn = ?, occurrence = occurrence + 1
                WHERE session_id = ? AND memory_key = ?
                """,
                (note, score, turn, session_id, memory_key),
            )
            row2 = self.conn.execute(
                """
                SELECT id FROM long_term_memory
                WHERE session_id = ? AND memory_key = ?
                """,
                (session_id, memory_key),
            ).fetchone()
            row_id = int(row2["id"])
        self.conn.commit()
        self._upsert_vector(row_id=row_id, text=note)

    def list_long_term(self, session_id: str) -> list[dict[str, Any]]:
        """세션 장기기억 목록을 중요도 순으로 반환한다."""
        rows = self.conn.execute(
            """
            SELECT memory_key, note, score, first_turn, last_turn, occurrence
            FROM long_term_memory
            WHERE session_id = ?
            ORDER BY score DESC, last_turn DESC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def retrieve_long_term(self, session_id: str, query_text: str, limit: int = 6) -> list[dict[str, Any]]:
        """장기기억 retrieval 통합 진입점.

        우선순위:
        1) 벡터 검색(sqlite-vec)
        2) lexical fallback
        """
        if self.vec_enabled:
            try:
                return self._retrieve_long_term_vector(session_id=session_id, query_text=query_text, limit=limit)
            except Exception:
                pass
        return self._retrieve_long_term_lexical(session_id=session_id, query_text=query_text, limit=limit)

    def _retrieve_long_term_vector(self, *, session_id: str, query_text: str, limit: int) -> list[dict[str, Any]]:
        """sqlite-vec 기반 의미 유사도 검색."""
        blob = self._serialize_embedding(self._embed(query_text))
        rows = self.conn.execute(
            """
            SELECT l.memory_key, l.note, l.score, l.first_turn, l.last_turn, l.occurrence,
                   v.distance
            FROM long_term_vec v
            JOIN long_term_memory l ON l.id = v.rowid
            WHERE l.session_id = ?
              AND v.embedding MATCH ?
            ORDER BY v.distance ASC, l.score DESC
            LIMIT ?
            """,
            (session_id, blob, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def _retrieve_long_term_lexical(self, *, session_id: str, query_text: str, limit: int) -> list[dict[str, Any]]:
        """간단 키워드 overlap 기반 lexical 검색."""
        tokens = [t for t in query_text.lower().split() if t]
        rows = self.conn.execute(
            """
            SELECT memory_key, note, score, first_turn, last_turn, occurrence
            FROM long_term_memory
            WHERE session_id = ?
            ORDER BY score DESC, last_turn DESC
            LIMIT 60
            """,
            (session_id,),
        ).fetchall()

        scored = []
        for row in rows:
            note = str(row["note"]).lower()
            overlap = sum(1 for tok in tokens if tok in note)
            scored.append((overlap, row["score"], dict(row)))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in scored[:limit]]

    def _upsert_vector(self, *, row_id: int, text: str) -> None:
        """long_term_memory 레코드와 long_term_vec 임베딩을 동기화한다."""
        if not self.vec_enabled:
            return
        try:
            blob = self._serialize_embedding(self._embed(text))
            self.conn.execute("DELETE FROM long_term_vec WHERE rowid = ?", (row_id,))
            self.conn.execute(
                "INSERT INTO long_term_vec(rowid, embedding) VALUES (?, ?)",
                (row_id, blob),
            )
            self.conn.commit()
        except Exception:
            # 벡터 인덱스 실패 시 기능을 중단하지 않고 본문 로직을 유지한다.
            self.vec_enabled = False

    def _embed(self, text: str) -> list[float]:
        """외부 모델 없이 deterministic hash embedding을 생성한다.

        주의: 품질보다 의존성 최소화/재현성을 위한 임시 임베딩이다.
        """
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        out: list[float] = []
        for i in range(self.VECTOR_DIM):
            b = seed[i % len(seed)]
            out.append((b / 255.0) * 2.0 - 1.0)
        return out

    def _serialize_embedding(self, vec: list[float]) -> bytes:
        """벡터를 sqlite-vec 호환 바이너리로 직렬화한다."""
        if sqlite_vec is not None:
            try:
                return sqlite_vec.serialize_float32(vec)
            except Exception:
                pass
        return struct.pack(f"<{len(vec)}f", *vec)
