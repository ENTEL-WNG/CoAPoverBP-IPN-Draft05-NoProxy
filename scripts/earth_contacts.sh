#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
require_file "$CONFIG_PY"
# Earth -> Satellite with reachability to Rover
"$CONFIG_PY" -m ud3tn_utils.aap2.bin.aap2_config \
    --socket /tmp/ud3tn-974848-earth.aap2.sock --agentid 14 \
    --schedule 1 3600 100000 --reaches ipn:974848.1.0 -vv \
    ipn:974848.2.0 tcpclv3:192.168.100.2:4772
