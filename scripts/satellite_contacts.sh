#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
require_file "$CONFIG_PY"
# Satellite -> Earth
"$CONFIG_PY" -m ud3tn_utils.aap2.bin.aap2_config \
  --socket /tmp/ud3tn-ipn3-sat.aap2.sock --agentid 13 \
  --schedule 1 3600 100000 -vv \
  ipn:0.3.0 tcpclv3:192.168.100.1:4673
# Satellite -> Rover
"$CONFIG_PY" -m ud3tn_utils.aap2.bin.aap2_config \
  --socket /tmp/ud3tn-ipn3-sat.aap2.sock --agentid 14 \
  --schedule 1 3600 100000 -vv \
  ipn:0.1.0 tcpclv3:192.168.100.3:4671
