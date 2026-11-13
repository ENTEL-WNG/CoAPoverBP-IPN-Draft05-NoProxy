#!/usr/bin/env bash
# Read-only local environment and repo-file checks; does not start daemons or change settings.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
problems=0
inspect() {
  local kind="$1" path="$2"
  if [[ -e "$path" ]]; then printf 'OK      %-17s %s\n' "$kind" "$path";
  else printf 'MISSING %-17s %s\n' "$kind" "$path"; problems=$((problems + 1)); fi
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
 rover) inspect 'Rover GUI Python' "$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python" ;;
 earth) inspect 'Earth Python' "$EARTH_PY" ;;
 satellite) : ;;
 '') echo 'TIP: Add rover|earth|satellite argument to inspect this VM role.' ;;
 *) echo 'Usage: scripts/check_setup.sh [rover|earth|satellite]' >&2; exit 2 ;;
esac
if [[ $problems -gt 0 ]]; then
  printf '\n%s check(s) need attention. See docs/installation.md\n' "$problems" >&2
  exit 1
fi
printf '\nAll selected file presence checks passed. This is NOT an end-to-end test.\n'
