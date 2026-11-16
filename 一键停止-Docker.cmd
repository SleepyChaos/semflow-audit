@echo off
setlocal
cd /d "%~dp0"
docker compose --env-file .env -f compose.yml -p semflow-audit down
exit /b %errorlevel%
