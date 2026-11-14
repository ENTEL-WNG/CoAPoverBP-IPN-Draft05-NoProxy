#!/usr/bin/env bash
# Shared paths. Explicit environment overrides make this reusable outside the old VM layout.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UD3TN_ROOT="${UD3TN_ROOT:-$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn}"
CONFIG_PY="${CONFIG_PY:-$HOME/coapbp/experiments/draft05-ipn/.venv-ipn/bin/python}"
ROVER_PY="${ROVER_PY:-$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python}"
EARTH_PY="${EARTH_PY:-$HOME/coapbp/experiments/draft05-ipn/.venv-coap310/bin/python}"
export PYTHONPATH="$REPO_ROOT/vendor/aiocoap/src:$UD3TN_ROOT/python-ud3tn-utils:$UD3TN_ROOT/pyd3tn${PYTHONPATH:+:$PYTHONPATH}"
require_file() { if [[ ! -f "$1" ]]; then printf 'Missing file: %s\n' "$1" >&2; exit 1; fi; }
