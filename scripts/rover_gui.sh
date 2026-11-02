#!/usr/bin/env bash
set -euo pipefail
WORK="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn"
PY="$HOME/coapbp/CoAPoverBP-no-proxy-version/ud3tn/.venv-app/bin/python"
GUI="$HOME/coapbp/experiments/draft05-ipn/Rover_Mission_Control_Draft05_Aggregation.py"
export PYTHONPATH="$WORK/python-ud3tn-utils:$WORK/pyd3tn"
exec "$PY" -u "$GUI"
