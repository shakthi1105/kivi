"""SQLite connection helpers for Kivi's word-memory store."""
import os
import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = APP_DIR / "schema.sql"
DEFAULT_DB_PATH = os.environ.get("KIVI_DB_PATH", str(APP_DIR.parent / "data" / "kivi.db"))


def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = None) -> None:
    conn = get_connection(db_path)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def reset_db(db_path: str = None) -> None:
    """Wipe all learned state. The schema is untouched; only rows are cleared."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM observations")
    conn.execute("DELETE FROM memory_entries")
    conn.commit()
    conn.close()
