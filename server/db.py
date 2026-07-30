"""SQLite 접속·초기화 헬퍼 (ORM 없이 stdlib sqlite3만 사용)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
DEFAULT_DB = ROOT_DIR / "data" / "club.db"

DB_PATH = Path(os.environ.get("JGPC_DB", DEFAULT_DB))


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def get_conn(path: Path | None = None):
    """요청 단위 커넥션. 예외 시 롤백."""
    conn = _connect(path or DB_PATH)
    try:
        yield conn
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def init_db(path: Path | None = None) -> Path:
    """스키마 적용 (idempotent)."""
    target = path or DB_PATH
    sql = (SERVER_DIR / "schema.sql").read_text(encoding="utf-8")
    conn = _connect(target)
    try:
        conn.executescript(sql)
    finally:
        conn.close()
    return target


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
