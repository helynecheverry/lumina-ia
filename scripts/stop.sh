#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for name in frontend api mongo; do
  file=".runtime/$name.pid"
  if [ -f "$file" ]; then
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      command="$(ps -p "$pid" -o args=)"
      case "$name:$command" in
        frontend:*streamlit*|frontend:*app.frontend*|api:*uvicorn*|mongo:*mongod*) kill "$pid" ;;
        *) echo "PID de $name no corresponde; no se detiene"; continue ;;
      esac
    fi
    rm -- "$file"
  fi
done
