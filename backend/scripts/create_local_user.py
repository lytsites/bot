from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="create_local_user",
        description="Create a local user (user/admin/superadmin) directly in the DB.",
    )
    p.add_argument("--login", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--role", required=True, choices=["user", "admin", "superadmin"])
    p.add_argument("--inactive", action="store_true", help="Create the user as inactive")
    p.add_argument(
        "--db",
        default=None,
        help="Override DB_PATH for this command (e.g. C:\\path\\to\\data.sqlite3).",
    )
    args = p.parse_args(argv)

    if args.db:
        os.environ["DB_PATH"] = args.db

    # Import after DB_PATH override so common.config picks it up consistently.
    from common.auth import hash_password
    from common.db import DB_PATH, init_db, db
    from common.users import ROLE_SUPER_ADMIN, create_local_user, role_from_str

    init_db()

    role = role_from_str(args.role)
    if role == ROLE_SUPER_ADMIN:
        # Allowed only via this CLI, not via web UI.
        pass

    with db() as con:
        user_id = create_local_user(
            con,
            login=args.login,
            password_hash=hash_password(args.password),
            role=role,
            is_active=not args.inactive,
        )

    print(f"ok: created local user id={user_id} role={args.role} login={args.login} db={DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
