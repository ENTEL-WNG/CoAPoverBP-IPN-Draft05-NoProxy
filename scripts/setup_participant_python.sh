#!/usr/bin/env bash
# Prepare a Python environment for the IETF 127 Experiment C Mission Control.
# Run this only in an independent clone / participant VM, not on the live lab.
# Usage: bash scripts/setup_participant_python.sh [--demo|--live]
# --demo: local Tkinter GUI, simulated traffic; does not need a µD3TN node.
# --live: Python dependencies for the real Rover engine; requires a separately
#         obtained and patched µD3TN tree with generated AAP2 Python bindings.
set -euo pipefail

MODE="${1:---demo}"
case "$MODE" in
  --demo|--live) ;;
  *) echo "Usage: bash scripts/setup_participant_python.sh [--demo|--live]" >&2; exit 2 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUI="$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/mission_control_v2_live_metrics.py"
VENV="$REPO_ROOT/.venv"
UD3TN_ROOT="${UD3TN_ROOT:-$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn}"

if [[ ! -f "$GUI" ]]; then
  echo "Missing current Mission Control GUI: $GUI" >&2
  exit 1
fi

# Prefer Python 3.10, the version used for the prepared lab's application.
# Override with PYTHON_BIN=/path/to/python3.10 if necessary.
if [[ -n "${PYTHON_BIN:-}" ]]; then
  BASE_PY="$PYTHON_BIN"
elif command -v python3.10 >/dev/null 2>&1; then
  BASE_PY="$(command -v python3.10)"
else
  BASE_PY="$(command -v python3 || true)"
fi
if [[ -z "$BASE_PY" ]] || ! "$BASE_PY" -c 'import sys; assert sys.version_info >= (3,10)' 2>/dev/null; then
  echo 'Python 3.10 or newer is required. Install it and set PYTHON_BIN=/path/to/python3.10.' >&2
  exit 1
fi

# Tkinter comes from the operating-system Python installation, not pip.
if ! "$BASE_PY" -c 'import tkinter' >/dev/null 2>&1; then
  echo 'Tkinter is unavailable for the selected Python.' >&2
  echo 'On Ubuntu install the matching python3-tk package, then retry.' >&2
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating participant virtual environment: $VENV"
  "$BASE_PY" -m venv "$VENV" || {
    echo 'venv creation failed: install the matching python3.x-venv package.' >&2
    exit 1
  }
fi
PY="$VENV/bin/python"
if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
  echo 'Tkinter is unavailable inside the new virtual environment.' >&2
  echo 'Install tkinter for the Python used to create .venv, then recreate .venv.' >&2
  exit 1
fi

if [[ "$MODE" == --demo ]]; then
  echo 'DEMO Python environment ready. No network connection or µD3TN service is needed.'
  echo "Next: cd '$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package'"
  echo '      bash ./run_gui_congestion_results.sh --demo'
  echo 'DEMO is simulated: do not report its measurements as experimental evidence.'
  exit 0
fi

# The repo does not contain the full µD3TN source/binary or generated AAP2
# bindings. Do not silently replace these with unrelated PyPI packages.
AAP2_SRC="$UD3TN_ROOT/python-ud3tn-utils"
if [[ ! -f "$AAP2_SRC/ud3tn_utils/aap2/aap2_client.py" ]]; then
  echo "Patched µD3TN AAP2 Python sources were not found at: $AAP2_SRC" >&2
  echo 'Obtain/build the compatible patched µD3TN project in a separate directory,' >&2
  echo 'then rerun with UD3TN_ROOT=/absolute/path/to/patched/ud3tn.' >&2
  echo 'A GitHub clone of this CoAP/BPv7 repository is not sufficient for LIVE mode.' >&2
  exit 1
fi

# The modified aiocoap sources are already vendored under vendor/aiocoap/src.
# Import them from that directory; do not pip-install stock aiocoap over them.
echo 'Installing Python-side LIVE dependencies into the local virtual environment ...'
"$PY" -m pip install 'protobuf==5.28.3' 'cbor2' 'aioconsole==0.8.2' 'Pillow' 'crcmod'

export PYTHONPATH="$REPO_ROOT/vendor/aiocoap/src:$AAP2_SRC:$UD3TN_ROOT/pyd3tn${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PY" -c 'import tkinter, aiocoap, aioconsole; from ud3tn_utils.aap2 import AAP2AsyncUnixClient; from ud3tn_utils.aap2.generated import aap2_pb2; print("LIVE Python imports: OK")'; then
  echo 'Live Python imports failed; verify generated AAP2 protobuf bindings,' >&2
  echo 'the patched µD3TN revision, and dependency compatibility.' >&2
  exit 1
fi

echo 'LIVE Python dependencies passed import checks.'
echo 'This does NOT mean the three-node DTN is running or that end-to-end delivery works.'
echo 'On the configured Rover VM, with the three-node lab already running:'
echo "  cd '$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package'"
echo '  bash ./run_gui_congestion_results.sh'
