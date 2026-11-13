# Reproduction quick start — IETF 127, IPN allocator 974848

**Project:** Experimental direct CoAP over BPv7 (Draft-05), RFC 9758 three-component `ipn:` endpoint identifiers, µD3TN/AAP2, TCPCLv3, **no CoAP-to-UDP proxy**.

This page is a **quick reference for the already-prepared three-VM laboratory**, not a tested clean-install recipe for participants. Read [installation.md](installation.md) for the environment requirements and [ietf-demo.md](ietf-demo.md) for detailed experiments, packet analysis and the ON/OFF challenge.

> **Protect the running experiment.** If the Rover Mission Control GUI, Earth application, or µD3TN daemons are already running, **reuse them**. Do **not** start duplicate daemons or GUIs, pull/switch Git branches on live VMs, overwrite AAP2 sockets, or replace GUI-managed contacts just to follow this page. The updated scripts belong to the `IPN_RFC_9758_Hackathon` GitHub branch; they are **not automatically installed** in the running VM checkout.

## Current topology

| VM | Internal IP (`enp0s8`) | Node EID | TCPCLv3 port | AAP2 socket |
| --- | --- | --- | ---: | --- |
| Rover | `192.168.100.3` | `ipn:974848.1.0` | `4771` | `/tmp/ud3tn-974848-rover.aap2.sock` |
| Satellite | `192.168.100.2` | `ipn:974848.2.0` | `4772` | `/tmp/ud3tn-974848-sat.aap2.sock` |
| Earth | `192.168.100.1` | `ipn:974848.3.0` | `4773` | `/tmp/ud3tn-974848-earth.aap2.sock` |

Rover application EIDs: **Safety** `ipn:974848.1.10`, **Science** `ipn:974848.1.11`. The Earth **CoAP application** is `ipn:974848.3.64` (not the bare Earth node `ipn:974848.3.0`). The Satellite forwards BPv7 bundles in both directions; it is **not** a CoAP proxy.

## Step 1 — Check what is already running

On the relevant VM, run this **read-only** command:

```bash
ps -eo pid,args | grep -E '[u]d3tn|[m]ission_control_v2|[N]odeB_Mission'
```

Check the `enp0s8` addresses and VM clocks if traffic is missing. In an independent copy of the Hackathon branch, `./scripts/check_setup.sh` can inspect the presence of required files and local binaries. **Passing that script is not evidence of end-to-end CoAP/BPv7 success.**

## Step 2 — Start daemons and forwarding contacts (fresh, idle, authorized lab ONLY)

**Skip this entire step if the testbed/GUI is already active.** The commands below apply to a prepared checkout of branch `IPN_RFC_9758_Hackathon`. Run the appropriate line on the **named VM**, from the repository root (`~/CoAPoverBP-IPN-Draft05-NoProxy`). Keep each daemon's terminal open.

```text
# First start the patched µD3TN daemon on each corresponding VM:
SATELLITE: ./scripts/start_ud3tn.sh satellite
EARTH:     ./scripts/start_ud3tn.sh earth
ROVER:     ./scripts/start_ud3tn.sh rover

# In separate terminals, configure four direction-specific forwarding contacts:
SATELLITE: ./scripts/satellite_contacts.sh   # Satellite → Earth and Satellite → Rover
EARTH:     ./scripts/earth_contacts.sh       # Earth → Satellite, reachable Rover
ROVER:     ./scripts/rover_contacts.sh       # Rover → Satellite, reachable Earth
```

These contact scripts use **3,600-second** schedules with a `100000`-byte contact volume parameter. They do **not** themselves implement an ON/OFF experiment. Renew contacts only when appropriate for the controlled run; do not override intentional GUI-managed link states. Check actual routing/TCPCL traffic rather than inferring delivery from a successful command exit.

## Step 3 — Earth application and latest Rover GUI

**On Earth, only if the CoAP server is not already running:**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_server.sh
```

This launcher selects `applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py`. The working Earth VM may already run that same application from its original directory under `~/coapbp/experiments/draft05-ipn/`; **do not start both copies**.

**On Rover, only if Mission Control is not already open:**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This is the working **Experiment C Mission Control v2** route. It uses `mission_control_v2_live_metrics.py`, the `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py` engine, and the Rover AAP2 socket `/tmp/ud3tn-974848-rover.aap2.sock`.

**Do not use `./scripts/rover_gui.sh` for the latest demo**: that launcher points to a historical Rover GUI. The Experiment C launcher also contains environment-specific absolute paths, so it is **not a portable one-command participant installer**.

The GUI starts at **NSTART=1**. Controlled GUI controls may switch to **NSTART=2** for a two-request Aggregate. The experiment-specific two-message aggregation buffer has an approximately **10-second** deadline. Two clicks do **not** by themselves prove aggregation, and NSTART=2 is **not** a demonstrated congestion-safety guarantee.

## Step 4 — Observe BPv7 and embedded CoAP with Wireshark on Earth

Use **Wireshark 4.6.9** where available and the repository Lua plugin `wireshark/coapbp05_ipn64_PL65000.lua` to inspect experimental CoAP fields. Wireshark's native BPv7 dissector handles the three-component RFC 9758 IPN EID fields.

- **Native Wireshark:** Capture directly on Earth `enp0s8` if your installation exposes that interface and has capture permissions. The relevant TCPCLv3 port is **4773**.
- **Flatpak Wireshark without visible interfaces:** From the repository root, run `bash wireshark/wireshark-ipn-live.sh enp0s8`. This launches Wireshark and feeds live host capture to it. The helper calls `tcpdump` internally; the participant need not run `tcpdump` separately.
- Install the Lua file in the **Personal Lua Plugins** directory shown by **Help → About Wireshark → Folders** for your actual installation, and restart Wireshark. Set **Analyze → Decode As** for TCPCLv3 if the traffic is not decoded automatically.

Useful **display filters** (enter separately):

```text
tcp.port == 4773
bpv7
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 2
```

Inspect BPv7 source/destination EIDs, one or two decoded CoAP members, their MIDs, Tokens and Payload-length fields. Save a `.pcapng` file, and correlate any response packets with the **same-run** Rover/Earth logs.

## Step 5 — Demonstrate Single, Aggregate and ON/OFF experiments

| Mode | Participant task | What to verify |
| --- | --- | --- |
| **Single** | In NSTART=1/Single mode, send a Safety NON GET or Science NON POST. | One request bundle, a valid application EID, response code and a matching Token if delivered back to Rover. |
| **Aggregate** | In a controlled mode allowing NSTART=2, send two requests from the **same Rover application EID** to Earth within the aggregation window. | **One BPv7 request bundle with two distinct CoAP members**; independent MIDs/Tokens; separate Single response bundles from Earth. |
| **ON/OFF contact** | With the lab owner's authorization, use the **existing GUI contact controls** to introduce and restore an OFF interval. | Record the contact state, submission/arrival times, queueing delay, return delivery and any expiration or loss. Do not assume queued bundles are delivered without evidence. |

**Recorded current example — allocator `974848`:** The updated [Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) documents a **59-byte** Safety Single BP payload, **102-byte** Science Single BP payload, and a **212-byte** Science Aggregate with two NON POST members (50-byte Payload-length per member), plus separately Token-matched responses in the recorded tests. These are **specific recorded observations**, not fixed sizes for every GUI run.

**Historical allocator-`0` evidence only:** Older tests recorded a **116-byte Safety Aggregate** and **556-byte Science Aggregate**, using ports `4671–4673`. Do **not** use those sizes, old MIDs or old frame numbers as expectations for the current allocator-`974848` experiment.

## Step 6 — Preserve evidence and recognize limitations

For every run record the branch/source revision, VM addresses, contact ON/OFF schedule, actual NSTART mode, request MIDs/Tokens, Earth responses, Rover Token matches, `.pcapng` filename and timestamps. Distinguish **submitted locally**, **arrived at Earth**, and **response received at Rover**.

The `65000` Payload-length option is **experimental**, response aggregation is not shown in the recorded path, and the newer setup has **not been independently reproduced from a clean checkout**. For detailed protocol limitations and the walkthrough, see [ietf-demo.md](ietf-demo.md), [installation.md](installation.md) and [results.md](results.md).

