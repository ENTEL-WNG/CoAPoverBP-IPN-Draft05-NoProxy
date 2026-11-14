#!/usr/bin/env bash
# IETF 127 participant environment (source this file in each new terminal).
# Intended for a NEW, separately prepared Ubuntu Rover/Satellite/Earth VM.
# Usage: source scripts/participant_env.sh
# This script ONLY exports environment variables and performs read-only checks.
# It does NOT install packages, change IPs, change contacts, or start/stop nodes.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf 'Please SOURCE this script so its variables remain in your terminal:\n' >&2
  printf '  source scripts/participant_env.sh\n' >&2
  exit 2
fi

_IETF127_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IETF127_REPO_ROOT="$(cd "$_IETF127_DIR/.." && pwd)"
export IETF127_REPO_ROOT

# Default location installed by scripts/prepare_participant_ud3tn.sh.
# If installed elsewhere, set UD3TN_ROOT BEFORE sourcing this file.
export UD3TN_ROOT="${UD3TN_ROOT:-$HOME/ietf127-participant/CoAPoverBP-no-proxy-version/ud3tn}"

# Virtual environment created by scripts/setup_participant_python.sh --live.
# Existing environment overrides are preserved, so this does not replace a
# deliberate per-node interpreter choice.
export CONFIG_PY="${CONFIG_PY:-$IETF127_REPO_ROOT/.venv/bin/python}"
export EARTH_PY="${EARTH_PY:-$IETF127_REPO_ROOT/.venv/bin/python}"
export ROVER_PY="${ROVER_PY:-$IETF127_REPO_ROOT/.venv/bin/python}"
export ROVER_GUI_PY="${ROVER_GUI_PY:-$IETF127_REPO_ROOT/.venv/bin/python}"

# Vendored modified aiocoap MUST take precedence over stock aiocoap.
export PYTHONPATH="$IETF127_REPO_ROOT/vendor/aiocoap/src:$UD3TN_ROOT/python-ud3tn-utils:$UD3TN_ROOT/pyd3tn${PYTHONPATH:+:$PYTHONPATH}"

printf 'IETF 127 participant environment loaded (no processes changed).\n'
printf '  Hackathon repository : %s\n' "$IETF127_REPO_ROOT"
printf '  Patched uD3TN tree   : %s\n' "$UD3TN_ROOT"
printf '  Contact config Python: %s\n' "$CONFIG_PY"
printf '  Earth server Python  : %s\n' "$EARTH_PY"
printf '  Rover GUI Python     : %s\n' "$ROVER_GUI_PY"

if [[ ! -x "$UD3TN_ROOT/build/posix/ud3tn" ]]; then
  printf '  NOT READY: patched uD3TN binary is missing.\n' >&2
  printf '  First run: bash scripts/prepare_participant_ud3tn.sh\n' >&2
fi
if [[ ! -x "$IETF127_REPO_ROOT/.venv/bin/python" ]]; then
  printf '  NOT READY: repository .venv is missing.\n' >&2
  printf '  Run: bash scripts/setup_participant_python.sh --live\n' >&2
fi
printf '  Network addresses and AAP2 services must be configured separately.\n'
unset _IETF127_DIR
