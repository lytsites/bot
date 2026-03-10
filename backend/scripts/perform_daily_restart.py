from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging
from common.system_status_file import clear_system_status_restarting, set_system_status_restarting
from common.system_flags import clear_system_restarting, set_system_restarting
from common.timezone import now_almaty, to_iso_local


setup_logging()
logger = get_logger("daily.restart")


def main() -> int:
    init_db()
    restart_until = to_iso_local(now_almaty() + timedelta(minutes=10))
    with db() as con:
        set_system_restarting(con, reason="daily_restart")
    set_system_status_restarting(reason="daily_restart", until=restart_until)
    try:
        logger.info("starting daily backend restart")
        subprocess.run(
            ["systemctl", "restart", "tg-auth.service", "tg-main.service", "tg-ai.service", "tg-worker.service"],
            check=True,
            timeout=180,
        )
        logger.info("daily backend restart completed")
    finally:
        clear_system_status_restarting()
        with db() as con:
            clear_system_restarting(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
