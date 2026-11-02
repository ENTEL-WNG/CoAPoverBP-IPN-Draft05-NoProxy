# Reproduction quick start

This is the **known working three-VM lab recipe**, not a certified clean-machine installer. Read [installation.md](installation.md) first to obtain a patched µD3TN build and compatible Python environments; then follow [ietf-demo.md](ietf-demo.md) for the detailed experiment and Wireshark walkthrough.

**All commands below run on the VM indicated, and in the repository directory.** Keep the daemon in its own running terminal. Do not start duplicate daemons on occupied ports or sockets.

```text
SATELLITE: ./scripts/start_ud3tn.sh satellite
EARTH:     ./scripts/start_ud3tn.sh earth
ROVER:     ./scripts/start_ud3tn.sh rover

SATELLITE: ./scripts/satellite_contacts.sh
EARTH:     ./scripts/earth_contacts.sh
ROVER:     ./scripts/rover_contacts.sh

EARTH:     ./scripts/earth_server.sh
ROVER:     ./scripts/rover_gui.sh
```

On Earth, capture on **enp0s8**, TCP port **4673**, decode TCPCLv3 → BPv7, and display filter `bpv7`. For the Lua parser of two-member Aggregates: `coapbp05.count == 2`. Click the **Safety GET** button twice within **10 s** for an expected **116-byte** aggregate or **Science POST** twice for an expected **556-byte** aggregate. These are specific to the supplied experimental payloads and code. Look for independently matched response Tokens.

The scripts support overrides `UD3TN_ROOT`, `CONFIG_PY`, `ROVER_PY`, and `EARTH_PY`. They are **not** a complete environment installer. The GUI's rover photo remains an external asset and state files are stored outside the repository; see installation notes.
