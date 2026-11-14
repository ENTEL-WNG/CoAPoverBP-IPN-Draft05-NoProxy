#!/usr/bin/env bash
# IETF 127 Experiment C Mission Control launcher.
# Usage: bash run_gui_congestion_results.sh [--demo|--preview|--live]
# --demo: simulated GUI; no µD3TN or AAP2 required.
# --live: real Rover AAP2 engine; prepared Rover/Satellite/Earth lab required.
set -euo pipefail

GUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GUI_DIR/../.." && pwd)"
UD3TN_ROOT="${UD3TN_ROOT:-$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn}"
ENGINE="$GUI_DIR/experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py"
SOCKET="${ROVER_AAP2_SOCKET:-/tmp/ud3tn-974848-rover.aap2.sock}"
MODE="${1:---live}"

case "$MODE" in
  --demo|--preview|--live) ;;
  *) echo "Usage: bash $0 [--demo|--preview|--live]" >&2; exit 2 ;;
esac

# An explicit Python choice wins; otherwise use a repository virtualenv,
# the prepared Rover laboratory virtualenv, or the system Python.
if [[ -n "${ROVER_GUI_PY:-}" ]]; then
  PY="$ROVER_GUI_PY"
elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif [[ -x "$UD3TN_ROOT/.venv-protoc-modern/bin/python" ]]; then
  PY="$UD3TN_ROOT/.venv-protoc-modern/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "No usable Python interpreter. Set ROVER_GUI_PY=/path/to/python." >&2
  exit 1
fi

# Ensure this checkout's modified aiocoap wins over any stock installation.
export PYTHONPATH="$GUI_DIR/.gui-live-deps:$REPO_ROOT/vendor/aiocoap/src:$UD3TN_ROOT/python-ud3tn-utils${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PY" -c 'import tkinter'; then
  echo "Tkinter is missing for $PY. Install python3-tk (Ubuntu) or use a Python with Tk support." >&2
  exit 1
fi

if [[ "$MODE" != --live ]]; then
  echo "Opening Mission Control $MODE (no real BPv7 requests will be sent)."
  exec "$PY" "$GUI_DIR/mission_control_v2_live_metrics.py" "$MODE"
fi

# Live mode must never auto-fall-back to a simulation.
if pgrep -af '[m]ission_control_v2_live_metrics.py --live|[m]ission_control_v2_compact.py|[R]over_Mission_Control_Draft05_Aggregation.py' >/dev/null; then
  echo 'Another Rover GUI is running. Close that GUI first; do not stop µD3TN.' >&2
  exit 1
fi
if [[ ! -f "$ENGINE" ]]; then
  echo "Missing current Rover engine: $ENGINE" >&2
  exit 1
fi
if [[ ! -S "$SOCKET" ]]; then
  echo "Rover AAP2 socket not found: $SOCKET" >&2
  echo 'Live mode needs the patched Rover µD3TN node, active contacts and Earth server.' >&2
  exit 1
fi
if ! "$PY" -c 'import aiocoap, aioconsole; from ud3tn_utils.aap2 import AAP2AsyncUnixClient'; then
  echo 'Missing live Python dependencies. Install patched ud3tn_utils, aioconsole, and modified aiocoap in the selected environment.' >&2
  echo "Python interpreter: $PY" >&2
  exit 1
fi

RUN_ID="$(date -u +'%Y%m%dT%H%M%SZ')"
RAW_DIR="$REPO_ROOT/Results/raw"
mkdir -p "$RAW_DIR" "$REPO_ROOT/Results/charts" "$REPO_ROOT/Results/tables"
CC_LIMIT=1
printf '{"run_id":"%s","gui_cc_limit":%d,"assessment_required_for_nstart2":true,"description":"CoAP NON Safety/Science; BPv7 TCPCL; 3 VMs"}\n' "$RUN_ID" "$CC_LIMIT" > "$RAW_DIR/${RUN_ID}_config.json"
echo "LIVE Experiment C: RUN_ID=$RUN_ID; starting at NSTART=1"
echo 'Agents remain running. This launcher does not stop µD3TN or the Earth server.'

if "$PY" "$GUI_DIR/mission_control_v2_live_metrics.py" --live --live-capture \
    --engine "$ENGINE" \
    --socket "$SOCKET" \
    --capture-bind "${ROVER_CAPTURE_BIND:-192.168.100.3}" \
    --capture-port "${ROVER_CAPTURE_PORT:-56786}" \
    --capture-jsonl "$RAW_DIR/${RUN_ID}.jsonl" \
    --cc-limit "$CC_LIMIT" \
    --cc-min-gap-ms "${IETF127_CC_MIN_GAP_MS:-100}" \
    --sol 42; then
  STATUS=0
else
  STATUS=$?
fi

# Charts are optional. Preserve the GUI's exit status if charting fails.
if [[ -f "$REPO_ROOT/Results/scripts/generate_results.py" ]]; then
  "$PY" "$REPO_ROOT/Results/scripts/generate_results.py" \
    --root "$REPO_ROOT/Results" \
    --events "$RAW_DIR/${RUN_ID}_events.jsonl" \
    --metrics "$RAW_DIR/${RUN_ID}.jsonl" \
    --nstart "$CC_LIMIT" || echo 'Optional result charts could not be generated.' >&2
fi
exit "$STATUS"
