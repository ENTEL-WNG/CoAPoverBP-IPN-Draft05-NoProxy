#!/usr/bin/env bash
# Run on each named VM in a separate long-lived terminal; never duplicate a running daemon.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
case "${1:-}" in
  rover)
    NODE='ipn:974848.1.0'; PORT=4771; SOCK='/tmp/ud3tn-974848-rover' ;;
  satellite)
    NODE='ipn:974848.2.0'; PORT=4772; SOCK='/tmp/ud3tn-974848-sat' ;;
  earth)
    NODE='ipn:974848.3.0'; PORT=4773; SOCK='/tmp/ud3tn-974848-earth' ;;
  *) echo 'Usage: scripts/start_ud3tn.sh rover|satellite|earth' >&2; exit 2 ;;
esac
require_file "$UD3TN_ROOT/build/posix/ud3tn"
printf 'Starting PATCHED µD3TN %s TCPCLv3 port %s\n' "$NODE" "$PORT"
exec "$UD3TN_ROOT/build/posix/ud3tn" \
  --node-id "$NODE" \
  --aap-socket "${SOCK}.aap1.sock" \
  --aap2-socket "${SOCK}.aap2.sock" \
  --cla "tcpclv3:*,${PORT}" \
  --bp-version 7 \
  --log-level 4
