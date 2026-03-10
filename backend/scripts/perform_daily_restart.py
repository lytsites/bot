from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging
from common.system_flags import clear_system_restarting, set_system_restarting


setup_logging()
logger = get_logger("daily.restart")


def main() -> int:
    init_db()
    with db() as con:
        set_system_restarting(con, reason="daily_restart")
    try:
        logger.info("starting daily backend restart")
        subprocess.run(
            ["systemctl", "restart", "tg-auth.service", "tg-main.service", "tg-ai.service", "tg-worker.service"],
            check=True,
            timeout=180,
        )
        logger.info("daily backend restart completed")
    finally:
        with db() as con:
            clear_system_restarting(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
