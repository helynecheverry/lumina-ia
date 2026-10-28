#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python}"
mkdir -p .runtime/logs .runtime/mongo
if ! "$PYTHON_BIN" -c 'from pymongo import MongoClient; MongoClient("mongodb://127.0.0.1:27017",serverSelectionTimeoutMS=1000).admin.command("ping")' >/dev/null 2>&1; then
  if [ ! -x .runtime/bin/mongod ]; then
    echo 'Falta MongoDB: ejecuta bash scripts/setup_mongo.sh'; exit 1
  fi
  .runtime/bin/mongod --dbpath "$PWD/.runtime/mongo" --bind_ip 127.0.0.1 --port 27017 --logpath "$PWD/.runtime/logs/mongo.log" --pidfilepath "$PWD/.runtime/mongo.pid" --fork
fi
start_service() {
  local name="$1"; shift
  if [ -f ".runtime/$name.pid" ] && kill -0 "$(cat ".runtime/$name.pid")" 2>/dev/null; then
    echo "$name ya está iniciado"; return
  fi
  nohup setsid "$@" >".runtime/logs/$name.log" 2>&1 </dev/null &
  echo $! >".runtime/$name.pid"
}
start_service api "$PYTHON_BIN" -m uvicorn app.api:app --host 127.0.0.1 --port 8000
start_service frontend "$PYTHON_BIN" -m uvicorn app.frontend:app --host 127.0.0.1 --port 8501
for service_url in http://127.0.0.1:8000/health http://127.0.0.1:8501/_stcore/health; do
  if ! curl --fail --silent --retry 20 --retry-connrefused --retry-delay 1 "$service_url" >/dev/null; then
    echo "No se pudo iniciar $service_url; revisa .runtime/logs"; exit 1
  fi
done
echo 'Interfaz: http://127.0.0.1:8501 · API: http://127.0.0.1:8000/docs'
