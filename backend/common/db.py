import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from common.config import DB_PATH


def now_iso() -> str:
    return datetime.utcnow().isoformat()

def _ensure_db_dir() -> None:
    try:
        raw = str(DB_PATH or "").strip()
        if not raw or raw == ":memory:":
            return
        p = Path(raw)
        parent = p.parent
        if parent and str(parent) not in (".", ""):
            parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Never block the app from starting because of a best-effort dir creation.
        pass


def init_db() -> None:
    _ensure_db_dir()
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
                    _ensure_is_admin_column(con)
                elif version == "013":
                    # sender_phone already added
                    pass
                elif version == "023":
                    # role already added
                    pass
                elif version == "031":
                    # support_notice_seen_at already added
                    pass
                elif version == "034":
                    # pending_buffer_until_at already added
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
    _ensure_db_dir()
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


def _ensure_is_admin_column(con: sqlite3.Connection) -> None:
    try:
        con.execute("ALTER TABLE local_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
