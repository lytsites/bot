from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging
from common.service_restarts import RESTARTABLE_SERVICES_BY_KEY
from common.system_flags import clear_system_restarting, set_system_restarting
from common.timezone import now_iso


setup_logging()
logger = get_logger("restart.requests")


def _load_pending_requests(con):
    return con.execute(
        """
        SELECT id, service_key, system_unit, requested_by_user_id, requested_at
        FROM service_restart_requests
        WHERE status='PENDING'
        ORDER BY requested_at ASC, id ASC
        """
    ).fetchall()


def _mark_processing(con, request_id: int) -> None:
    con.execute(
        "UPDATE service_restart_requests SET status='PROCESSING' WHERE id=? AND status='PENDING'",
        (request_id,),
    )


def _mark_done(con, request_id: int) -> None:
    con.execute(
        """
        UPDATE service_restart_requests
        SET status='DONE', processed_at=?, error_message=NULL
        WHERE id=?
        """,
        (now_iso(), request_id),
    )


def _mark_failed(con, request_id: int, message: str) -> None:
    con.execute(
        """
        UPDATE service_restart_requests
        SET status='FAILED', processed_at=?, error_message=?
        WHERE id=?
        """,
        (now_iso(), str(message or "RESTART_FAILED")[:2000], request_id),
    )


def main() -> int:
    init_db()
    processed = 0
    with db() as con:
        rows = _load_pending_requests(con)
    for row in rows:
        request_id = int(row["id"])
        service_key = str(row["service_key"] or "").strip()
        system_unit = str(row["system_unit"] or "").strip()
        service = RESTARTABLE_SERVICES_BY_KEY.get(service_key)
        if not service or service.unit != system_unit:
            with db() as con:
                _mark_failed(con, request_id, "UNKNOWN_SERVICE")
            continue
        with db() as con:
            _mark_processing(con, request_id)
        try:
            logger.info("processing restart request id=%s service=%s unit=%s", request_id, service_key, system_unit)
            with db() as con:
                set_system_restarting(con, reason=f"manual_restart:{service_key}")
            completed = subprocess.run(
                ["systemctl", "restart", system_unit],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if completed.stdout:
                logger.info("restart request id=%s stdout=%s", request_id, completed.stdout.strip())
            if completed.stderr:
                logger.info("restart request id=%s stderr=%s", request_id, completed.stderr.strip())
            with db() as con:
                _mark_done(con, request_id)
            processed += 1
        except Exception as exc:
            logger.exception("restart request failed id=%s service=%s", request_id, service_key)
            with db() as con:
                _mark_failed(con, request_id, f"{type(exc).__name__}: {exc}")
        finally:
            with db() as con:
                clear_system_restarting(con)
    logger.info("restart request processor finished processed=%s", processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
