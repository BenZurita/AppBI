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

# ============================================
# CONFIGURACIÓN DE RUTAS
# ============================================

# Agregar ruta personalizada al PYTHONPATH
#export PYTHONPATH="/usr/lib/python3/dist-packages/gunicorn:$PYTHONPATH"
export PYTHONPATH="/usr/lib/python3:$PYTHONPATH"

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
echo "  Directory: $DIR"
echo "  Workers:   $WORKERS"
echo "  Bind:      $HOST:$PORT"
echo "  Log level: $LOG_LEVEL"
echo "  PYTHONPATH: $PYTHONPATH"
echo "========================="

# ============================================
# ✅ ACTIVAR ENTORNO VIRTUAL (CRÍTICO)
# ============================================


# Intentar múltiples ubicaciones comunes para el venv
VENV_FOUND=""

if [ -f "venv/bin/activate" ]; then
    VENV_PATH="venv"
    VENV_FOUND="yes"
elif [ -f "../venv/bin/activate" ]; then
    VENV_PATH="../venv"
    VENV_FOUND="yes"
elif [ -f "/opt/gif-app/venv/bin/activate" ]; then
    VENV_PATH="/opt/gif-app/venv"
    VENV_FOUND="yes"
elif [ -f "/opt/gif-app/AppBI/venv/bin/activate" ]; then
    VENV_PATH="/opt/gif-app/AppBI/venv"
    VENV_FOUND="yes"
fi

# Si no se encontró, buscar dinámicamente
if [ -z "$VENV_FOUND" ]; then
    VENV_PATH=$(find /opt/gif-app -name "activate" -type f 2>/dev/null | head -1)
    if [ -n "$VENV_PATH" ]; then
        VENV_PATH=$(dirname $(dirname "$VENV_PATH"))
        VENV_FOUND="yes"
    fi
fi

# Si todavía no se encontró, error
if [ -z "$VENV_FOUND" ]; then
    echo "❌ Error: No se encontró virtual environment"
    echo "   Buscando en:"
    echo "   - $DIR/venv/bin/activate"
    echo "   - $DIR/../venv/bin/activate"
    echo "   - /opt/gif-app/venv/bin/activate"
    echo "   - /opt/gif-app/AppBI/venv/bin/activate"
    echo ""
    echo "   Ejecuta: find /opt/gif-app -name 'activate' -type f"
    exit 1
fi

echo "✅ Virtualenv encontrado en: $VENV_PATH"

# Activar entorno virtual
source "$VENV_PATH/bin/activate"
echo "✅ Virtualenv activado"
echo "   Python: $(which python)"
echo "   Gunicorn: $(which gunicorn)"
echo "   Gunicorn version: $(gunicorn --version 2>&1 | head -1)"











# ============================================
# VERIFICAR DEPENDENCIAS CRÍTICAS
# ============================================

echo ""
echo "=== Verificando dependencias ==="
python -c "from dotenv import load_dotenv" 2>/dev/null && echo "✅ python-dotenv OK" || { echo "❌ python-dotenv NO instalado"; exit 1; }
python -c "import fastapi" 2>/dev/null && echo "✅ fastapi OK" || { echo "❌ fastapi NO instalado"; exit 1; }
python -c "import uvicorn" 2>/dev/null && echo "✅ uvicorn OK" || { echo "❌ uvicorn NO instalado"; exit 1; }

# ============================================
# EJECUTAR GUNICORN
# ============================================

echo ""
echo "=== Iniciando Gunicorn ==="

# ============================================
# ✅ ACTIVAR ENTORNO VIRTUAL (CRÍTICO)
# ============================================

# ============================================
# ✅ ACTIVAR ENTORNO VIRTUAL (CRÍTICO)
# ============================================

# Intentar múltiples ubicaciones comunes para el venv
if [ -f "venv/bin/activate" ]; then
    VENV_PATH="venv"
elif [ -f "../venv/bin/activate" ]; then
    VENV_PATH="../venv"
elif [ -f "/opt/gif-app/AppBI/venv/bin/activate" ]; then
    VENV_PATH="/opt/gif-app/AppBI/venv"
elif [ -f "/opt/gif-app/venv/bin/activate" ]; then
    VENV_PATH="/opt/gif-app/venv"
else
    echo "❌ Error: No se encontró virtual environment"
    echo "   Buscando en:"
    echo "   - $DIR/venv/bin/activate"
    echo "   - $DIR/../venv/bin/activate"
    echo "   - /opt/gif-app/AppBI/venv/bin/activate"
    echo "   - /opt/gif-app/venv/bin/activate"
    exit 1
fi

echo "✅ Virtualenv encontrado en: $VENV_PATH"

# Activar entorno virtual
source "$VENV_PATH/bin/activate"
echo "✅ Virtualenv activado"
echo "   Python: $(which python)"
echo "   Gunicorn: $(which gunicorn)"
echo "   Gunicorn version: $(gunicorn --version 2>&1 | head -1)"

# ============================================
# VERIFICAR DEPENDENCIAS CRÍTICAS
# ============================================

echo ""
echo "=== Verificando dependencias ==="
python -c "from dotenv import load_dotenv" 2>/dev/null && echo "✅ python-dotenv OK" || { echo "❌ python-dotenv NO instalado"; exit 1; }
python -c "import fastapi" 2>/dev/null && echo "✅ fastapi OK" || { echo "❌ fastapi NO instalado"; exit 1; }
python -c "import uvicorn" 2>/dev/null && echo "✅ uvicorn OK" || { echo "❌ uvicorn NO instalado"; exit 1; }



# ============================================
# VERIFICAR DEPENDENCIAS CRÍTICAS
# ============================================

echo ""
echo "=== Verificando dependencias ==="
python -c "from dotenv import load_dotenv" 2>/dev/null && echo "✅ python-dotenv OK" || { echo "❌ python-dotenv NO instalado"; exit 1; }
python -c "import fastapi" 2>/dev/null && echo "✅ fastapi OK" || { echo "❌ fastapi NO instalado"; exit 1; }
python -c "import uvicorn" 2>/dev/null && echo "✅ uvicorn OK" || { echo "❌ uvicorn NO instalado"; exit 1; }
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
