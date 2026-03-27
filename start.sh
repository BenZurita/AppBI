#!/bin/bash
# start.sh — Iniciar App BI con Gunicorn + Uvicorn workers
#
# Uso:
#   chmod +x start.sh
#   ./start.sh
#
# Variables de entorno opcionales:
#   WORKERS   — Número de workers (default: 4)
#   HOST      — IP de escucha (default: 0.0.0.0)
#   PORT      — Puerto (default: 8000)
#   LOG_LEVEL — Nivel de log: debug, info, warning, error (default: info)

set -e

# Directorio del script
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Configuración
WORKERS="${WORKERS:-4}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "=== App BI — Starting ==="
echo "  Workers:   $WORKERS"
echo "  Bind:      $HOST:$PORT"
echo "  Log level: $LOG_LEVEL"
echo "========================="

exec gunicorn main:app \
    --workers "$WORKERS" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "$HOST:$PORT" \
    --log-level "$LOG_LEVEL" \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5
