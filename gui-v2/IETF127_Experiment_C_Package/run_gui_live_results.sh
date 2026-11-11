#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd ../.. && pwd)"
if pgrep -af '[m]ission_control_v2_live_metrics.py --live|[m]ission_control_v2_compact.py|[R]over_Mission_Control_Draft05_Aggregation.py' >/dev/null; then
  echo 'Another Rover GUI is running. Close its window first; do not stop µD3TN.'
  exit 1
fi
PY="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python"
if [[ ! -x "$PY" ]]; then echo "Missing Python environment: $PY"; exit 1; fi
export PYTHONPATH="$PWD/.gui-live-deps:$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/python-ud3tn-utils:$HOME/CoAPoverBP-IPN-Draft05-NoProxy/vendor/aiocoap/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c 'import tkinter,aioconsole,aiocoap; from ud3tn_utils.aap2 import AAP2AsyncUnixClient'
RUN_ID="$(date -u +'%Y%m%dT%H%M%SZ')"
RAW_DIR="$REPO_ROOT/Results/raw"
mkdir -p "$RAW_DIR" "$REPO_ROOT/Results/charts" "$REPO_ROOT/Results/tables" "$REPO_ROOT/Demo video"
# Begin with NSTART=1 every run; the GUI mode buttons switch the actual
# in-memory NodeA engines to NSTART=2 and back at runtime.
CC_LIMIT=1
CC_ARGS=()
printf '{"run_id":"%s","gui_cc_limit":%d,"assessment_required_for_nstart2":true,"description":"CoAP NON Safety/Science; BPv7 TCPCL; 3 VMs"}\n' "$RUN_ID" "$CC_LIMIT" > "$RAW_DIR/${RUN_ID}_config.json"
echo "RUN_ID=$RUN_ID; CONFIGURED GUI NSTART CEILING=$CC_LIMIT"
echo "Data: $RAW_DIR/${RUN_ID}.jsonl (live metrics), ${RUN_ID}_events.jsonl (application and bundle events)"
echo 'Agents remain running; do not stop µD3TN or NodeB.'
"$PY" mission_control_v2_live_metrics.py --live --live-capture \
  --engine "$HOME/CoAPoverBP-IPN-Draft05-NoProxy/applications/rover/NodeA_Mission_Draft05_Aggregation.py" \
  --socket /tmp/ud3tn-ipn3-lab.aap2.sock --capture-bind 192.168.100.3 --capture-port 56786 \
  --capture-jsonl "$RAW_DIR/${RUN_ID}.jsonl" --cc-limit "$CC_LIMIT" "${CC_ARGS[@]}" \
  --cc-min-gap-ms "${IETF127_CC_MIN_GAP_MS:-100}" --sol 42
STATUS=$?
echo "GUI closed; generating actual-run charts (where sufficient data exists) ..."
python3 "$REPO_ROOT/Results/scripts/generate_results.py" --root "$REPO_ROOT/Results" \
  --events "$RAW_DIR/${RUN_ID}_events.jsonl" --metrics "$RAW_DIR/${RUN_ID}.jsonl" --nstart "$CC_LIMIT" || true
exit "$STATUS"
