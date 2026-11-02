# Reproduction guide — known commands

These scripts are example commands from the working three-VM lab. Start the actual modified µD3TN daemon on each VM **using the original verified command and the correct node EID and port**, then start the Earth server and Rover GUI using the included scripts. AAP2 configuration is issued from separate terminals and must be refreshed after its one-hour contact expires.

1. On Satellite, run `scripts/satellite_contacts.sh`.
2. On Earth, run `scripts/earth_contacts.sh`; start `scripts/earth_server.sh`.
3. On Rover, run `scripts/rover_contacts.sh`; start `scripts/rover_gui.sh`.
4. On Earth, capture **enp0s8**, TCP port **4673**; Decode As TCPCLv3 if necessary and apply display filter `bpv7`.
5. Press Rover Safety GET **twice within 10 s** for a 116-byte Aggregate; press Science POST **twice within 10 s** for a 556-byte Aggregate.
6. Save `.pcapng` and record both Earth and Rover console logs from the *same run*, exact MIDs, Tokens, BP lifetime and time stamps.
7. Install `wireshark/coapbp05_ipn64_PL65000.lua` into Earth's `~/.local/lib/wireshark/plugins/`, restart Wireshark, and use filter `coapbp05.count == 2`. The decoder covers destination IPN services **10, 11, 64**.

Scripts do not install dependencies or start µD3TN; they depend on the tested VM environments in `~/coapbp`. For a portable release, document installation, dependencies, daemon startup, build steps and full end-to-end validation.
