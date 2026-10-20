#!/usr/bin/env bash
# Instala PlotCraft en un entorno virtual y lo agrega al menú de aplicaciones.
# Uso:  bash scripts/install.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Falta python3-venv. Instálalo con:  sudo apt install python3-venv" >&2
    exit 1
fi
if command -v dpkg >/dev/null 2>&1 && ! dpkg -s libxcb-cursor0 >/dev/null 2>&1; then
    echo "Aviso: falta libxcb-cursor0, que Qt necesita para abrir la ventana." >&2
    echo "       Instálalo con:  sudo apt install libxcb-cursor0" >&2
fi

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e .
.venv/bin/python -m plotcraft --install-launcher
echo
echo "Listo. Busca «PlotCraft» en el menú de aplicaciones, o ejecuta: .venv/bin/plotcraft"
