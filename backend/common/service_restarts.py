from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


RESTART_COOLDOWN_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class RestartableService:
    key: str
    label: str
    unit: str
    restart_timeout: timedelta


RESTARTABLE_SERVICES: tuple[RestartableService, ...] = (
    RestartableService(key="main_api", label="Бэкенд", unit="tg-main.service", restart_timeout=timedelta(minutes=3)),
    RestartableService(key="auth_api", label="Авторизация", unit="tg-auth.service", restart_timeout=timedelta(minutes=3)),
    RestartableService(key="ai_api", label="AI API", unit="tg-ai.service", restart_timeout=timedelta(minutes=3)),
    RestartableService(key="worker", label="Воркеры", unit="tg-worker.service", restart_timeout=timedelta(minutes=5)),
)

RESTARTABLE_SERVICES_BY_KEY = {item.key: item for item in RESTARTABLE_SERVICES}
