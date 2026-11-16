#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$ROOT_DIR/一键启动-Docker.sh"
result=$?
if [[ $result -ne 0 ]]; then
  read -r -p "Startup failed. Press Enter to close. "
fi
exit "$result"
