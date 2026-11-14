#!/usr/bin/env bash
# IETF 127: set/check the isolated VirtualBox internal-network IPv4 address.
# Intended ONLY for newly created participant VMs, never for the running lab.
# Requirements: Adapter 1 NAT; Adapter 2 Internal Network named "intnet".
# Usage:
#   bash scripts/participant_vm_network.sh --check rover|satellite|earth
#   IETF127_FRESH_VM=YES bash scripts/participant_vm_network.sh --configure rover|satellite|earth
# This only adds a temporary IPv4 address to the existing internal interface.
# It does NOT change DNS, NAT, default routes, VirtualBox settings or contacts.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: bash scripts/participant_vm_network.sh --check|--configure rover|satellite|earth

  --check       Read-only inspection of the selected VM's internal interface.
  --configure   On a NEW participant VM ONLY: add its role-specific static IPv4.
                Requires IETF127_FRESH_VM=YES as an explicit safety guard.

VirtualBox prerequisites (configure in VirtualBox, not in this script):
  Adapter 1: NAT
  Adapter 2: Internal Network, name exactly intnet

Expected addresses:
  rover:      192.168.100.3/24
  satellite:  192.168.100.2/24
  earth:      192.168.100.1/24

Addresses added by --configure are temporary until reboot. This tool does
not enable persistent Netplan or NetworkManager configuration.
HELP
}

if [[ $# -ne 2 ]]; then usage >&2; exit 2; fi
MODE="$1"
ROLE="$2"
case "$MODE" in --check|--configure) ;; *) usage >&2; exit 2 ;; esac
case "$ROLE" in
  rover) IP='192.168.100.3'; PEERS=('192.168.100.2' '192.168.100.1');;
  satellite) IP='192.168.100.2'; PEERS=('192.168.100.3' '192.168.100.1');;
  earth) IP='192.168.100.1'; PEERS=('192.168.100.2' '192.168.100.3');;
  *) usage >&2; exit 2 ;;
esac
IFACE="${IETF127_NET_IFACE:-enp0s8}"

command -v ip >/dev/null 2>&1 || { echo 'Missing ip command (iproute2).' >&2; exit 1; }
if ! ip link show dev "$IFACE" >/dev/null 2>&1; then
  echo "Interface $IFACE not found." >&2
  echo 'Check Adapter 2 in VirtualBox and confirm the actual interface name with: ip -br link' >&2
  exit 1
fi

current_ipv4() {
  ip -o -4 addr show dev "$IFACE" scope global | awk '{print $4}'
}

show_status() {
  printf '\nVM role: %-10s Expected: %s/24 on %s\n' "$ROLE" "$IP" "$IFACE"
  ip -br link show dev "$IFACE"
  ip -br -4 addr show dev "$IFACE"
  printf 'Existing IPv4: %s\n' "$(current_ipv4 | paste -sd ', ' - || true)"
}

show_status
if [[ "$MODE" == --check ]]; then
  result=0
  if current_ipv4 | grep -Fxq "$IP/24"; then
    echo 'PASS: this VM has the intended static internal-network address.'
  else
    echo 'NOT READY: expected address is not configured. No changes made.'
    result=1
  fi
  echo 'After all three VMs have addresses and Adapter 2 uses intnet, check peers:'
  for peer in "${PEERS[@]}"; do echo "  ping -c 2 $peer"; done
  exit "$result"
fi

if [[ "${IETF127_FRESH_VM:-}" != 'YES' ]]; then
  echo 'REFUSED: configuring an IP address requires IETF127_FRESH_VM=YES.' >&2
  echo 'Never use --configure on an active Hackathon Rover/Satellite/Earth VM.' >&2
  exit 1
fi

# Refuse to modify a working daemon or active GUI, regardless of VM label.
if command -v ss >/dev/null 2>&1 && ss -ltn | grep -Eq ':(4771|4772|4773)[[:space:]]'; then
  echo 'REFUSED: a Hackathon TCPCL port is listening. No changes made.' >&2
  exit 1
fi
for socket in /tmp/ud3tn-974848-{rover,sat,earth}.aap2.sock; do
  if [[ -S "$socket" ]]; then
    echo "REFUSED: active AAP2 socket detected: $socket" >&2
    exit 1
  fi
done

assigned="$(current_ipv4)"
if printf '%s\n' "$assigned" | grep -Fxq "$IP/24"; then
  echo 'Address already present. No changes necessary.'
  exit 0
fi
if [[ -n "$assigned" ]]; then
  echo "REFUSED: $IFACE already has an IPv4 address ($assigned). No changes made." >&2
  echo 'Review the interface and address manually before proceeding.' >&2
  exit 1
fi

command -v sudo >/dev/null 2>&1 || { echo 'sudo is required to assign a new IP address.' >&2; exit 1; }
echo "Assigning $IP/24 to $IFACE on this NEW $ROLE VM (not persistent) ..."
sudo ip link set dev "$IFACE" up
sudo ip address add "$IP/24" dev "$IFACE"
show_status
echo 'Configured for this boot. Repeat --check and test ping after all three VMs are ready.'
