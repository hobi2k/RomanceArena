from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PersistedSession:
    session_id: str
    npc_id: str
    turn: int
    player_name: str
    saved: bool
    npc_emotion: str
    saya_fsm_state: str


class SessionStore:
    """SQLite 기반 세션 저장소.

    Args:
        db_path: SQLite 파일 경로.

    Returns:
        SessionStore: 세션 영속화를 담당하는 저장소 객체.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                npc_id TEXT NOT NULL,
                turn INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                saved INTEGER NOT NULL,
                npc_emotion TEXT NOT NULL DEFAULT 'neutral',
                saya_fsm_state TEXT NOT NULL DEFAULT 'guarded',
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_saved ON sessions(saved)")
        cols = {r["name"] for r in cur.execute("PRAGMA table_info(sessions)").fetchall()}
        if "npc_emotion" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN npc_emotion TEXT NOT NULL DEFAULT 'neutral'")
        if "saya_fsm_state" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN saya_fsm_state TEXT NOT NULL DEFAULT 'guarded'")
        self.conn.commit()

    def upsert(
        self,
        *,
        session_id: str,
        npc_id: str,
        turn: int,
        player_name: str,
        saved: bool,
        npc_emotion: str,
        saya_fsm_state: str,
    ) -> None:
        """세션 상태를 저장/갱신한다.

        Args:
            session_id: 세션 식별자.
            npc_id: NPC 식별자.
            turn: 현재 턴.
            player_name: 플레이어 이름.
            saved: 사용자 저장 여부.

        Returns:
            None.
        """
        self.conn.execute(
            """
            INSERT INTO sessions(session_id, npc_id, turn, player_name, saved, npc_emotion, saya_fsm_state, updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                npc_id=excluded.npc_id,
                turn=excluded.turn,
                player_name=excluded.player_name,
                saved=excluded.saved,
                npc_emotion=excluded.npc_emotion,
                saya_fsm_state=excluded.saya_fsm_state,
                updated_at=excluded.updated_at
            """,
            (
                session_id,
                npc_id,
                int(turn),
                player_name,
                1 if saved else 0,
                str(npc_emotion or "neutral"),
                str(saya_fsm_state or "guarded"),
                _utc_now(),
            ),
        )
        self.conn.commit()

    def mark_saved(self, session_id: str) -> bool:
        """세션을 저장 완료 상태로 마킹한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            bool: 갱신 성공 여부.
        """
        cur = self.conn.execute(
            "UPDATE sessions SET saved=1, updated_at=? WHERE session_id=?",
            (_utc_now(), session_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete(self, session_id: str) -> bool:
        """세션을 삭제한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            bool: 삭제 성공 여부.
        """
        cur = self.conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def delete_unsaved(self) -> int:
        """미저장 세션을 일괄 삭제한다.

        Args:
            없음.

        Returns:
            int: 삭제된 세션 수.
        """
        cur = self.conn.execute("DELETE FROM sessions WHERE saved=0")
        self.conn.commit()
        return int(cur.rowcount)

    def get(self, session_id: str) -> Optional[PersistedSession]:
        """세션 상태를 조회한다.

        Args:
            session_id: 세션 식별자.

        Returns:
            Optional[PersistedSession]: 세션 존재 시 레코드, 없으면 None.
        """
        cur = self.conn.execute(
            "SELECT session_id, npc_id, turn, player_name, saved, npc_emotion, saya_fsm_state FROM sessions WHERE session_id=?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return PersistedSession(
            session_id=row["session_id"],
            npc_id=row["npc_id"],
            turn=int(row["turn"]),
            player_name=row["player_name"],
            saved=bool(int(row["saved"])),
            npc_emotion=str(row["npc_emotion"] or "neutral"),
            saya_fsm_state=str(row["saya_fsm_state"] or "guarded"),
        )
