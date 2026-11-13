#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
require_file "$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh"
exec bash "$REPO_ROOT/gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh"
