@echo off
setlocal
call :start
set "result=%errorlevel%"
if not "%result%"=="0" (
  echo Startup failed. Check Docker Desktop and the messages above.
  pause
)
exit /b %result%

:start
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is required. Install and start Docker Desktop, then run this script again.
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is not running or the current user cannot access Docker.
  exit /b 1
)

if not exist ".env" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 system\scripts\init_local.py
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo No .env found and Python is unavailable. Install Python 3 or create .env first.
      exit /b 1
    )
    python system\scripts\init_local.py
  )
  if errorlevel 1 exit /b 1
)

docker compose --env-file .env -f compose.yml -p semflow-audit up -d --build --wait
if errorlevel 1 exit /b 1
docker compose --env-file .env -f compose.yml -p semflow-audit ps -a
if errorlevel 1 exit /b 1

echo.
echo SemFlow Audit is running:
for /f "delims=" %%A in ('docker compose --env-file .env -f compose.yml -p semflow-audit port frontend 80') do echo   Workbench: http://%%A
for /f "delims=" %%A in ('docker compose --env-file .env -f compose.yml -p semflow-audit port backend 8000') do echo   API docs: http://%%A/docs
exit /b 0
