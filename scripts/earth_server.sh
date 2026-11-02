#!/usr/bin/env bash
set -euo pipefail
WORK="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn"
PY="$HOME/coapbp/experiments/draft05-ipn/.venv-coap310/bin/python"
SERVER="$HOME/coapbp/experiments/draft05-ipn/NodeB_Mission_Draft05_IPN.py"
export PYTHONPATH="$WORK/python-ud3tn-utils:$WORK/pyd3tn"
exec "$PY" -u "$SERVER"
