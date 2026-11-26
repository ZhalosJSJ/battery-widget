#!/usr/bin/env bash
# Activa el entorno virtual y corre el widget de batería.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual (usa paquetes del sistema para dbus-python)..."
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python main.py
