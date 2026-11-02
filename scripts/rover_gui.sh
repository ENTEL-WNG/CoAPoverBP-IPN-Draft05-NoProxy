#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
require_file "$ROVER_PY"
require_file "$REPO_ROOT/applications/rover/Rover_Mission_Control_Draft05_Aggregation.py"
exec "$ROVER_PY" -u "$REPO_ROOT/applications/rover/Rover_Mission_Control_Draft05_Aggregation.py"
