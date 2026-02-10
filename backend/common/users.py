from __future__ import annotations

from typing import Optional

from ai.defaults import load_new_local_user_defaults
from common.db import now_iso


ROLE_USER = 0
ROLE_ADMIN = 1
ROLE_SUPER_ADMIN = 2


def role_from_str(v: str | None) -> int:
    v = (v or "").strip().lower()
    if v in ("user", "пользователь"):
        return ROLE_USER
    if v in ("admin", "админ"):
        return ROLE_ADMIN
    if v in ("superadmin", "super_admin", "super-admin", "суперадмин", "супер-админ", "супер админ"):
        return ROLE_SUPER_ADMIN
    raise ValueError("INVALID_ROLE")


def role_to_str(role: int) -> str:
    if int(role) == ROLE_SUPER_ADMIN:
        return "superadmin"
    if int(role) == ROLE_ADMIN:
        return "admin"
    return "user"


def get_user_role(con, user_id: int) -> int:
    # Be defensive for older DBs (pre-role migration).
    try:
        row = con.execute("SELECT role FROM local_users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return ROLE_USER
        return int(row["role"] or 0)
    except Exception:
        row = con.execute("SELECT is_admin FROM local_users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return ROLE_USER
        return ROLE_ADMIN if int(row["is_admin"] or 0) == 1 else ROLE_USER


def create_local_user(
    con,
    *,
    login: str,
    password_hash: str,
    role: int,
    is_active: bool = True,
    service_enabled: bool = True,
    feature_group_reading_enabled: bool = True,
    feature_auto_dialogs_enabled: bool = True,
    disabled_comment: Optional[str] = None,
) -> int:
    now = now_iso()
    defaults = load_new_local_user_defaults()

    # Legacy: is_admin flag stays for older UI/client usage.
    is_admin = 1 if int(role) >= ROLE_ADMIN else 0

    # Insert local user.
    try:
        con.execute(
            """
            INSERT INTO local_users(
              login, password_hash, is_active, is_admin, role,
              service_enabled, feature_group_reading_enabled, feature_auto_dialogs_enabled, disabled_comment,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                login,
                password_hash,
                1 if is_active else 0,
                is_admin,
                int(role),
                1 if service_enabled else 0,
                1 if feature_group_reading_enabled else 0,
                1 if feature_auto_dialogs_enabled else 0,
                (disabled_comment or "").strip() or None,
                now,
                now,
            ),
        )
    except Exception:
        # If DB doesn't have the new columns yet (or even role column), fall back.
        # This keeps CLI/scripts from hard-crashing on older DBs.
        try:
            con.execute(
                """
                INSERT INTO local_users(login, password_hash, is_active, is_admin, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (login, password_hash, 1 if is_active else 0, is_admin, int(role), now, now),
            )
        except Exception:
            con.execute(
                """
                INSERT INTO local_users(login, password_hash, is_active, is_admin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (login, password_hash, 1 if is_active else 0, is_admin, now, now),
            )

    user_row = con.execute("SELECT last_insert_rowid() AS id").fetchone()
    user_id = int(user_row["id"])

    # Base settings rows.
    con.execute(
        """
        INSERT OR IGNORE INTO local_user_settings(user_id, keywords, is_active, created_at, updated_at)
        VALUES (?, '', 1, ?, ?)
        """,
        (user_id, now, now),
    )

    con.execute(
        """
        INSERT OR IGNORE INTO local_user_auto_chat_settings(
          user_id, ai_instruction, greeting_examples, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, defaults.ai_instruction, defaults.greeting_examples, now, now),
    )

    # Simulation columns may not exist on older DBs; update defensively.
    try:
        con.execute(
            """
            UPDATE local_user_auto_chat_settings
            SET delay_enabled=?, delay_min_ms=?, delay_max_ms=?, typing_enabled=?, read_enabled=?, updated_at=?
            WHERE user_id=?
            """,
            (
                defaults.delay_enabled,
                defaults.delay_min_ms,
                defaults.delay_max_ms,
                defaults.typing_enabled,
                defaults.read_enabled,
                now,
                user_id,
            ),
        )
    except Exception:
        pass

    return user_id


def can_manage_users(actor_role: int) -> bool:
    return int(actor_role) >= ROLE_ADMIN


def can_create_admins(actor_role: int) -> bool:
    return int(actor_role) >= ROLE_SUPER_ADMIN


def can_delete_target(actor_role: int, target_role: int) -> bool:
    actor_role = int(actor_role)
    target_role = int(target_role)
    if actor_role < ROLE_ADMIN:
        return False
    if actor_role == ROLE_ADMIN:
        return target_role == ROLE_USER
    # super-admin
    return target_role in (ROLE_USER, ROLE_ADMIN)
