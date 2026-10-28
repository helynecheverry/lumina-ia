#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" -m venv --system-site-packages .runtime/modern
.runtime/modern/bin/python -m pip install -r requirements-modern.txt
.runtime/modern/bin/python -c 'import json, diffusers; from diffusers import Flux2KleinPipeline, QwenImageEditPlusPipeline; print(json.dumps({"diffusers":diffusers.__version__,"flux_klein":True,"qwen_edit":True}))' > .runtime/modern/validated.json
echo 'Entorno de FLUX y Qwen preparado. Instala sus pesos únicamente en un equipo con recursos suficientes.'
