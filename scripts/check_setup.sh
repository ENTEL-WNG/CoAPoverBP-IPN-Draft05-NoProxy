#!/usr/bin/env bash
# Read-only checks of required repository files and local Python/uD3TN paths.
# This does not start/stop daemons or change any network/contact settings.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

problems=0
inspect() {
  local kind="$1" path="$2"
  if [[ -e "$path" ]]; then
    printf 'OK      %-20s %s\n' "$kind" "$path"
  else
    printf 'MISSING %-20s %s\n' "$kind" "$path"
    problems=$((problems + 1))
  fi
}

# Match the Python-selection order of the current Rover GUI launcher:
# explicitly selected ROVER_GUI_PY, then the repository .venv, then the
# prepared uD3TN lab interpreter, then system Python. None are modified.
rover_gui_python() {
  if [[ -n "${ROVER_GUI_PY:-}" ]]; then
    printf '%s\n' "$ROVER_GUI_PY"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$REPO_ROOT/.venv/bin/python"
  elif [[ -x "$UD3TN_ROOT/.venv-protoc-modern/bin/python" ]]; then
    printf '%s\n' "$UD3TN_ROOT/.venv-protoc-modern/bin/python"
  else
    command -v python3 || true
  fi
}

inspect 'Rover engine' "$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py"
inspect 'Rover GUI' "$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/mission_control_v2_live_metrics.py"
inspect 'Earth server' "$REPO_ROOT/applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py"
inspect 'Vendored aiocoap' "$REPO_ROOT/vendor/aiocoap/src/aiocoap/message.py"
inspect 'IPN patch' "$REPO_ROOT/patches/ud3tn/ipn-three-component-aap2.patch"
inspect 'Lua dissector' "$REPO_ROOT/wireshark/coapbp05_ipn64_PL65000.lua"
inspect 'BPv7 capture' "$REPO_ROOT/evidence/Earth_IPN974848_Single_and_Aggregate.pcapng"
inspect 'Patched µD3TN bin' "$UD3TN_ROOT/build/posix/ud3tn"
inspect 'Route Python' "$CONFIG_PY"

case "${1:-}" in
  rover)
    selected_python="$(rover_gui_python)"
    inspect 'Rover GUI Python' "$selected_python"
    ;;
  earth) inspect 'Earth Python' "$EARTH_PY" ;;
  satellite) : ;;
  '') echo 'TIP: Add rover|earth|satellite argument to inspect this VM role.' ;;
  *) echo 'Usage: bash scripts/check_setup.sh [rover|earth|satellite]' >&2; exit 2 ;;
esac

if [[ $problems -gt 0 ]]; then
  printf '\n%s check(s) need attention. See docs/installation.md\n' "$problems" >&2
  exit 1
fi
printf '\nAll selected file presence checks passed. This is NOT an end-to-end test.\n'

