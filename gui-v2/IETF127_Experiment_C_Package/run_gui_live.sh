#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if pgrep -af '[m]ission_control_v2_compact.py|[R]over_Mission_Control_Draft05_Aggregation.py|[m]ission_control_v2.py --live' >/dev/null; then
  echo 'An older GUI is still running. Close its window first (do not stop µD3TN).'
  pgrep -af '[m]ission_control_v2_compact.py|[R]over_Mission_Control_Draft05_Aggregation.py|[m]ission_control_v2.py --live' || true
  exit 1
fi
PY="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing working Python 3.10 environment: $PY"
  exit 1
fi
export PYTHONPATH="$PWD/.gui-live-deps:$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/python-ud3tn-utils:$HOME/CoAPoverBP-IPN-Draft05-NoProxy/vendor/aiocoap/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c 'import tkinter,aioconsole,aiocoap; from ud3tn_utils.aap2 import AAP2AsyncUnixClient' || {
  echo 'Missing GUI Python dependency. Do not alter system Python.'
  exit 1
}
exec "$PY" mission_control_v2_live_metrics.py \
  --live --live-capture \
  --engine "$HOME/CoAPoverBP-IPN-Draft05-NoProxy/applications/rover/NodeA_Mission_Draft05_Aggregation.py" \
  --socket /tmp/ud3tn-ipn3-lab.aap2.sock \
  --capture-bind 192.168.100.3 --capture-port 56786 \
  --capture-jsonl "$HOME/ietf127_evidence/live_metrics.jsonl" --sol 42
