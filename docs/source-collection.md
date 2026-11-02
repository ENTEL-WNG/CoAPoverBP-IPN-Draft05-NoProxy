# Source collection — completed initial repository snapshot

This checklist documents how the first GitHub commit was assembled **without modifying the live experiment**. It supersedes the pre-publication instructions from the original starter package.

- Rover experimental engine `NodeA_Mission_Draft05_Aggregation.py` and `Rover_Mission_Control_Draft05_Aggregation.py`: collected into `applications/rover/`.
- Earth server `NodeB_Mission_Draft05_IPN.py`: copied over SSH to `applications/earth/`.
- Verified nine-file C/AAP2 patch: `patches/ud3tn/ipn-three-component-aap2.patch`, recorded source base commit `37b968d5742cbd75292b534f3421fac70acc46b7`.
- Modified aiocoap source snapshot and package metadata: `vendor/aiocoap/`. Licensing text preserved in `vendor/aiocoap/LICENSES`.
- Final Lua dissector with service registrations **10/11/64**: `wireshark/coapbp05_ipn64_PL65000.lua`.
- Actual Earth Safety and Science Aggregate captures: `evidence/safety/` and `evidence/science/`.

Initial repository commit: **`539b63d`** (99 files); its local `main` branch was reported as tracking `origin/main`. The entire clone remains **not independently deployment-tested**. Updated docs and helper scripts in this documentation update should be committed as a separate subsequent commit.

Do not upload `.venv`, VM images, state JSON, database files, sockets, private keys or unreviewed application logs. Packet captures can reveal internal testbed addresses and payloads: the research group should approve any publication beyond the private repository.
