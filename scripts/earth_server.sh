#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
require_file "$EARTH_PY"
require_file "$REPO_ROOT/applications/earth/NodeB_Mission_Draft05_IPN.py"
exec "$EARTH_PY" -u "$REPO_ROOT/applications/earth/NodeB_Mission_Draft05_IPN.py"
