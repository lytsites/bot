@echo off
setlocal

set "HERE=%~dp0"

REM Usage examples:
REM   backend\create_local_user.bat --login user1 --password pass123 --role user
REM   backend\create_local_user.bat --login admin3 --password pass123 --role admin
REM   backend\create_local_user.bat --login root --password pass123 --role superadmin

py -3.11 "%HERE%scripts\\create_local_user.py" %*
if errorlevel 1 (
  exit /b 1
)
