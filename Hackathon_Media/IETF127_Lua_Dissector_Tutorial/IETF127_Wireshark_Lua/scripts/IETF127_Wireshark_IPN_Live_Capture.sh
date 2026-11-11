#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# IETF 127 Hackathon · CoAP over BPv7 · Wireshark 4.6.9 (Flatpak) live capture
#
# Streams live packets from a host interface into the sandboxed Wireshark
# Flatpak through a named pipe (FIFO):
#
#     <interface> ──► host tcpdump ──► named pipe ──► Wireshark 4.6.9 (Flatpak)
#
# This helper ONLY captures packets. It does not start, stop or modify µD3TN,
# AAP2 agents, contact schedules, the Rover GUI or any CoAP application.
#
# Usage:
#   ./IETF127_Wireshark_IPN_Live_Capture.sh [interface]        (default: enp0s8)
#   CAPTURE_FILTER='tcp port 4773' ./IETF127_Wireshark_IPN_Live_Capture.sh enp0s8
#
# Environment:
#   CAPTURE_FILTER   tcpdump capture filter (default: 'ip or ip6').
#                    Use the Earth TCPCLv3 port of YOUR run, e.g. 4773
#                    (current run) or 4673 (older repository baseline).
#   WIRESHARK_APP    Flatpak application ID (default: org.wireshark.Wireshark)
#
# Requirements: Linux, flatpak, tcpdump, iproute2 (ip), mkfifo, sudo rights
# for packet capture. Keep this terminal open for the whole capture.
# -----------------------------------------------------------------------------
set -euo pipefail

usage() {
  sed -n '3,24p' "$0" | sed 's/^# \{0,1\}//'
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

IFACE="${1:-enp0s8}"
APP="${WIRESHARK_APP:-org.wireshark.Wireshark}"
CAPTURE_FILTER="${CAPTURE_FILTER:-ip or ip6}"

# 1. Check required tools ------------------------------------------------------
for executable in flatpak tcpdump ip mkfifo sudo; do
  command -v "$executable" >/dev/null 2>&1 || {
    echo "Error: missing command '$executable'. Install it and try again." >&2
    exit 1
  }
done

# 2. Check the capture interface and the Wireshark Flatpak ---------------------
ip link show "$IFACE" >/dev/null 2>&1 || {
  echo "Error: no interface named '$IFACE'. List interfaces with: ip -br addr" >&2
  exit 1
}
flatpak info "$APP" >/dev/null 2>&1 || {
  echo "Error: Flatpak application '$APP' is not installed." >&2
  echo "       For a native Wireshark, capture '$IFACE' directly instead." >&2
  exit 1
}

# 3. Create a private named pipe the sandbox is allowed to read ---------------
PIPE_DIR="$HOME/.var/app/$APP/cache"
mkdir -p "$PIPE_DIR"
PIPE="$PIPE_DIR/${IFACE}-live-$$.fifo"
mkfifo -m 600 "$PIPE"

CAP_PID=''
cleanup() {
  if [[ -n "$CAP_PID" ]]; then
    kill "$CAP_PID" 2>/dev/null || true
    wait "$CAP_PID" 2>/dev/null || true
  fi
  rm -f -- "$PIPE"
}
trap cleanup EXIT INT TERM

printf 'Capture interface : %s\n' "$IFACE"
printf 'Capture filter    : %s\n' "$CAPTURE_FILTER"
printf 'Named pipe        : %s\n' "$PIPE"
printf 'Keep this terminal open while Wireshark captures. Close Wireshark to stop.\n'

# 4. Start tcpdump (unbuffered PCAP to the pipe) and open Wireshark -----------
sudo -v
# The pipe belongs to the user, so the redirect intentionally runs without sudo.
# shellcheck disable=SC2024
sudo -n tcpdump -i "$IFACE" -p -s 0 -U -w - "$CAPTURE_FILTER" > "$PIPE" &
CAP_PID=$!
flatpak run --filesystem="$PIPE_DIR" "$APP" -k -i "$PIPE"
