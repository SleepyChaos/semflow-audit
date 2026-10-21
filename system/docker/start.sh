#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
action=${1:-up}
case "$action" in up|doctor|down|logs) ;; *) echo 'Usage: sh system/docker/start.sh [up|doctor|down|logs]' >&2; exit 2;; esac
command -v docker >/dev/null 2>&1 || { echo 'Install and start Docker Desktop.' >&2; exit 1; }
os_type=$(docker info --format '{{.OSType}}')
[ "$os_type" = linux ] || { echo 'Docker must run Linux containers.' >&2; exit 1; }
docker compose version
if [ ! -f "$root/.env.docker" ]; then
    [ "$action" = up ] || { echo 'Run up first to create .env.docker.' >&2; exit 1; }
    password=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
    umask 077
    sed "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$password/" "$root/system/docker/compose.env.example" > "$root/.env.docker"
    echo 'Created .env.docker with a random database password. Add AI_API_KEY and rerun. Existing local settings were preserved.'
    exit 2
fi
compose() { docker compose --env-file "$root/.env.docker" -f "$root/system/compose.full.yml" "$@"; }
compose config --quiet
case "$action" in
    up)
        compose up -d --build --wait --wait-timeout 1800
        echo 'Startup complete. Default URL: http://localhost:5181 (or APP_PORT in .env.docker).'
        ;;
    doctor)
        compose ps -a
        echo 'Configuration parsed. Use logs for startup failures. Registry 502/timeouts require checking Docker Desktop proxy/mirror settings.'
        ;;
    down) compose down ;;
    logs) compose logs --tail 100 init validator validator-init api worker ;;
esac
