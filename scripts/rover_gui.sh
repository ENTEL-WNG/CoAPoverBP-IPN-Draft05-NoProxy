#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

GUI_LAUNCHER="$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh"

require_file "$GUI_LAUNCHER"

exec bash "$GUI_LAUNCHER" "$@"
