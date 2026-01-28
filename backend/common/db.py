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
        except sqlite3.IntegrityError as e:
            if version == "012" and "UNIQUE constraint failed" in str(e):
                _dedupe_group_matches(con)
                con.executescript(sql_text)
            else:
                raise
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                if version == "008":
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
                elif version == "005":
                    _ensure_auth_flow_columns(con)
                elif version == "016":
                    _ensure_admin_user(con)
                elif version == "013":
                    # sender_phone already added
                    pass
                else:
                    raise
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


def _ensure_auth_flow_columns(con: sqlite3.Connection) -> None:
    # Make 005 idempotent if columns already exist
    for col in ("method", "qr_token", "qr_expires_at", "qr_refresh_after", "error_message"):
        try:
            con.execute(f"ALTER TABLE auth_flows ADD COLUMN {col} TEXT;")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise


def _ensure_admin_user(con: sqlite3.Connection) -> None:
    try:
        con.execute("ALTER TABLE local_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
    con.execute(
        """
        INSERT OR IGNORE INTO local_users(login, password_hash, is_active, is_admin, created_at, updated_at)
        VALUES ('lyttern.lu@gmail.com',
                '1107c82fc14dcb88cbb262588d012d3958a13489aee45e2834cb64aec3b6d5ac',
                1, 1, ?, ?)
        """,
        (now_iso(), now_iso()),
    )
    con.execute(
        """
        INSERT OR IGNORE INTO local_user_settings(user_id, keywords, is_active, created_at, updated_at)
        SELECT id, '', 1, ?, ?
        FROM local_users
        WHERE login = 'lyttern.lu@gmail.com'
        """,
        (now_iso(), now_iso()),
    )
