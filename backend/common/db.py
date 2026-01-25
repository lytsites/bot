import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from common.config import DB_PATH


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def init_db() -> None:
    with sqlite3.connect(DB_PATH, timeout=10) as con:
        _configure_con(con)
        apply_migrations(con)


def apply_migrations(con: sqlite3.Connection) -> None:
    _configure_con(con)
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    con.commit()

    migrations_dir = Path(__file__).parent / "migrations"
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        row = con.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row:
            continue
        sql_text = path.read_text(encoding="utf-8")
        try:
            con.executescript(sql_text)
        except sqlite3.OperationalError as e:
            if version == "008" and "duplicate column name" in str(e):
                try:
                    con.execute("ALTER TABLE accounts ADD COLUMN local_user_id INTEGER;")
                except sqlite3.OperationalError as e2:
                    if "duplicate column name" not in str(e2):
                        raise
                con.execute(
                    """
                    UPDATE accounts
                    SET local_user_id = (SELECT id FROM local_users WHERE login='admin1')
                    WHERE local_user_id IS NULL
                      AND EXISTS (SELECT 1 FROM local_users WHERE login='admin1')
                    """
                )
            else:
                raise
        except sqlite3.IntegrityError as e:
            if version == "012" and "UNIQUE constraint failed" in str(e):
                _dedupe_group_matches(con)
                con.executescript(sql_text)
            else:
                raise
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, now_iso()),
        )
        con.commit()


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    _configure_con(con)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _configure_con(con: sqlite3.Connection) -> None:
    try:
        con.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass
    con.execute("PRAGMA busy_timeout=10000;")


def _dedupe_group_matches(con: sqlite3.Connection) -> None:
    con.execute(
        """
        DELETE FROM group_matches
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM group_matches
            GROUP BY account_id, chat_id, message_id
        )
        """
    )
