# Linux Deployment (production)

Этот проект переведен на Linux-режим без `.bat`/PowerShell watchdog.
Стабильность обеспечивается `systemd` (`Restart=always`) + `nginx`.

## 1. Что нужно на сервере

- Ubuntu/Debian сервер с root-доступом
- Домен и DNS записи:
  - `<frontend-host>` -> сервер
  - `api.<base-domain>` -> сервер
  - `auth.<base-domain>` -> сервер

Пример:
- frontend: `app.example.com`
- base-domain: `example.com`
- backend URL: `api.example.com`, `auth.example.com`

## 2. Клонирование проекта

```bash
git clone <YOUR_REPO_URL> /opt/tg-web-auth
cd /opt/tg-web-auth
```

## 3. Авто-настройка (root)

```bash
cd /opt/tg-web-auth
./deploy/linux/bootstrap_root.sh <base-domain> [frontend-host]
```

Пример:

```bash
./deploy/linux/bootstrap_root.sh example.com app.example.com
```

Скрипт:
- ставит системные пакеты (`python3`, `nginx`, `nodejs`, `npm`)
- создает системного пользователя `tgapp`
- поднимает venv и ставит Python-зависимости
- собирает фронт (`npm ci && npm run build`)
- устанавливает и запускает `systemd` сервисы
- ставит nginx-конфиг

## 4. Обязательная настройка `.env`

Проверь `/opt/tg-web-auth/.env`:

- `TG_API_ID`
- `TG_API_HASH`
- `SESSION_ENC_KEY`
- `DEEPSEEK_API_KEY`
- `FRONTEND_ORIGINS` (обязательно добавить ваш frontend URL)

Пример:

```env
FRONTEND_ORIGINS=https://app.example.com
DB_PATH=backend/var/data.sqlite3
LOG_PATH=backend/var/logs/app.log
```

После изменения `.env`:

```bash
systemctl restart tg-auth tg-main tg-ai tg-worker
```

## 5. TLS (рекомендуется)

```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d <frontend-host> -d api.<base-domain> -d auth.<base-domain>
```

## 6. Проверка состояния

```bash
systemctl status tg-auth tg-main tg-ai tg-worker tg-control-requests.timer tg-daily-restart.timer --no-pager
journalctl -u tg-main -n 100 --no-pager
journalctl -u tg-auth -n 100 --no-pager
journalctl -u tg-ai -n 100 --no-pager
journalctl -u tg-worker -n 100 --no-pager
journalctl -u tg-control-requests.service -n 100 --no-pager
journalctl -u tg-daily-restart.service -n 100 --no-pager
```

## 7. Ручные команды запуска (без systemd)

```bash
cd /opt/tg-web-auth
backend/run_main_service.sh
backend/run_auth_service.sh
backend/run_ai_service.sh
backend/run_worker_service.sh
```

## 8. Создание локального пользователя

```bash
cd /opt/tg-web-auth
backend/create_local_user.sh --login admin --password 'StrongPass123' --role superadmin
```

## 9. Обновление после git pull

```bash
cd /opt/tg-web-auth
git pull
sudo -u tgapp .venv/bin/pip install -r backend/requirements.txt
sudo -u tgapp bash -lc 'cd frontend && npm ci && npm run build'
systemctl restart tg-auth tg-main tg-ai tg-worker
systemctl reload nginx
```
