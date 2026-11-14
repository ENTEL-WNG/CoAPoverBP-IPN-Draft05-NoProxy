#!/usr/bin/env bash
# Earth / Linux participant helper: live enp0s8 capture into the Wireshark Flatpak.
# Captures packets only; it does not alter µD3TN, contact schedules or CoAP apps.
# Usage: bash wireshark/wireshark-ipn-live.sh [interface]
# Optional: CAPTURE_FILTER='tcp port 4773' bash wireshark/wireshark-ipn-live.sh enp0s8
set -euo pipefail
IFACE="${1:-enp0s8}"
APP='org.wireshark.Wireshark'
CAPTURE_FILTER="${CAPTURE_FILTER:-ip or ip6}"
for executable in flatpak tcpdump ip mkfifo; do
  command -v "$executable" >/dev/null 2>&1 || {
    echo "Missing command: $executable" >&2
    exit 1
  }
done
ip link show "$IFACE" >/dev/null 2>&1 || {
  echo "No interface named $IFACE. Check ip -br addr." >&2
  exit 1
}
PIPE_DIR="$HOME/.var/app/$APP/cache"
mkdir -p "$PIPE_DIR"
PIPE="$PIPE_DIR/enp0s8-live-$$.fifo"
mkfifo -m 600 "$PIPE"
CAP_PID=''
cleanup() {
  if [[ -n "$CAP_PID" ]]; then
    kill "$CAP_PID" 2>/dev/null || true
    wait "$CAP_PID" 2>/dev/null || true
  fi
  rm -f -- "$PIPE"
}
trap cleanup EXIT
printf 'Capture interface: %s\nCapture filter: %s\n' "$IFACE" "$CAPTURE_FILTER"
printf 'Keep this terminal open while Wireshark captures.\n'
sudo -v
sudo -n tcpdump -i "$IFACE" -p -s 0 -U -w - "$CAPTURE_FILTER" > "$PIPE" &
CAP_PID=$!
flatpak run --filesystem="$PIPE_DIR" "$APP" -k -i "$PIPE"
