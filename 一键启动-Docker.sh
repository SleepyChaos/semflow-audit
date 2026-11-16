#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install and start Docker Desktop, then run this script again." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running or the current user cannot access Docker." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "No .env found and python3 is unavailable. Install Python 3 or create .env first." >&2
    exit 1
  fi
  python3 system/scripts/init_local.py
fi

docker compose --env-file .env -f compose.yml -p semflow-audit up -d --build --wait
docker compose --env-file .env -f compose.yml -p semflow-audit ps -a

echo
echo "SemFlow Audit is running:"
FRONTEND_ADDRESS="$(docker compose --env-file .env -f compose.yml -p semflow-audit port frontend 80)"
API_ADDRESS="$(docker compose --env-file .env -f compose.yml -p semflow-audit port backend 8000)"
echo "  Workbench: http://${FRONTEND_ADDRESS}"
echo "  API docs:  http://${API_ADDRESS}/docs"
