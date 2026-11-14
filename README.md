
# CoAP over BPv7 — Draft-05, three-component IPN, no proxy

**IETF 127 Hackathon research prototype** · [CoAP over BPv7 Internet-Draft (draft-ietf-core-coap-bp-05)](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/) · [RFC 9758: three-component IPN](https://www.rfc-editor.org/rfc/rfc9758) · [RFC 9171: BPv7](https://www.rfc-editor.org/rfc/rfc9171)

This repository contains an **experimental implementation of direct CoAP over Bundle Protocol Version 7 (BPv7)** for a Rover–Satellite–Earth delay/disruption-tolerant network. CoAP applications use a modified **aiocoap** implementation and **µD3TN/AAP2** to send CoAP messages in BPv7 bundles over TCPCLv3.

**No CoAP-to-UDP proxy is used.**

The laboratory implementation and packet dissector are research prototypes, not a claim of complete draft conformance.

> **Current lab configuration (13 November 2026):** RFC 9758 **three-component `ipn:` EIDs with allocator `974848`**, TCPCLv3 ports **4771–4773**, and the **Experiment C Mission Control v2** GUI. A recorded allocator-974848 test demonstrated Single request/response exchanges and an Aggregate carrying two Science NON POST requests in one BPv7 payload, with separately matched Earth responses. Earlier allocator-`0` results are retained as **historical evidence**, not presented as measurements of the newer setup.

## Participant Handbook

**Start here:** [Download the IETF 127 Participant Lab Manual](Participant%20Handbook/IETF127_CoAP_over_BPv7_Participant_Lab_Manual.pdf) or see the [Participant Handbook folder](Participant%20Handbook/).

The handbook walks through cloning the **`IPN_RFC_9758_Hackathon`** branch, preparing three separate Rover, Satellite and Earth Ubuntu/VirtualBox VMs, installing the patched µD3TN and Python dependencies, configuring contacts, running the real Mission Control GUI, and verifying BPv7 bundles with Wireshark.

A fresh three-VM deployment has **not yet been independently reproduced end to end**. Use separate participant VMs; do not modify the live demonstration nodes.

## Three-VM architecture

```text
  ROVER                         SATELLITE                         EARTH
  192.168.100.3                 192.168.100.2                     192.168.100.1
  ipn:974848.1.0                ipn:974848.2.0                    ipn:974848.3.0
  TCPCLv3 :4771                 TCPCLv3 :4772                     TCPCLv3 :4773

  Safety  ipn:974848.1.10 --\
                              +---- BPv7 / TCPCLv3 relay ----> CoAP server
  Science ipn:974848.1.11 --/                               ipn:974848.3.64
                                                              GET /mission/safety-guidance
                                                              POST /science/observations
               <------------- BPv7 Single response bundles ---
```

| Node | Internal interface | Node EID | TCPCLv3 | Application EIDs |
| --- | --- | --- | ---: | --- |
| Rover | `enp0s8` · `192.168.100.3` | `ipn:974848.1.0` | 4771 | Safety `ipn:974848.1.10`; Science `ipn:974848.1.11` |
| Satellite | `enp0s8` · `192.168.100.2` | `ipn:974848.2.0` | 4772 | BP relay; **not** a CoAP proxy |
| Earth | `enp0s8` · `192.168.100.1` | `ipn:974848.3.0` | 4773 | CoAP server `ipn:974848.3.64` |

CoAP authorities follow the local `.ipn.alt` naming convention, for example:

- Safety: `coap://64.3.974848.ipn.alt/mission/safety-guidance`
- Science: `coap://64.3.974848.ipn.alt/science/observations`

The addresses above correspond to **allocator.node.service**.

The Earth CoAP application is `ipn:974848.3.64`, **not** the bare Earth node EID `ipn:974848.3.0`.

The prototype uses **NON (non-confirmable) CoAP** requests. It does not use the `dtn:` endpoint scheme.

## Current functional evidence — allocator 974848

The updated [Experiment C package](experiments/Experiment_C_Updated_IPN974848/README.md) documents the later three-component IPN implementation and preserves screenshots and measurements separately from the original allocator-`0` payload-size study.

| Observed test | BPv7 application payload | Verified observation |
| --- | ---: | --- |
| Safety Single GET | **59 B** | **4/4** Token-matched `2.05 Content` responses in the documented test |
| Science Single POST | **102 B** | **1/1** Token-matched `2.01 Created` response |
| Science Aggregate | **212 B** | **Two NON POST requests in one BPv7 bundle**; **2/2** Token-matched `2.01 Created` responses |
| BPv7 Primary Block | — | Captured **90,000 ms** bundle lifetime in the documented trace |
| RFC 9758 EID encoding | — | Wireshark displayed **IPN Element Count = 3**, allocator **974848**, and the expected node/service numbers |

In the recorded Science Aggregate:

- Both CoAP requests originated from the Science application EID `ipn:974848.1.11`.
- Both targeted the Earth CoAP application EID `ipn:974848.3.64`.
- Each POST used a **50-byte Payload-length**.
- The two member requests had distinct MIDs and Tokens.
- Both CoAP requests were transported inside **one BPv7 application payload**.
- Earth parsed the two requests and generated **two separate Single response bundles**.
- The recorded Rover-side responses were successfully matched using their Tokens.

These results describe **specific recorded tests**, not a general reliability, performance or interoperability guarantee.

For Wireshark screenshots, per-test evidence and separation of historical/current datasets, see [Experiment C](experiments/Experiment_C_Updated_IPN974848/README.md).

For capture instructions and the Lua dissector, see [Wireshark documentation](wireshark/README.md).

### Historical results — older allocator 0

Some older code examples, documents and captures use `ipn:0.*.*`, TCPCL ports `4671–4673`, and different payload sizes.

For example, earlier Safety and Science Aggregates had **116 B** and **556 B** application payloads, respectively.

These are **not the same run** as the 212 B Science Aggregate under allocator `974848`.

Do **not** mix packet-frame numbers, Tokens, metrics or efficiency percentages from the two configurations.

The original experiment's payload-size efficiency numbers are preserved in [Experiment C's historical section](experiments/Experiment_C_Updated_IPN974848/README.md#4-historical-payload-size-comparison--allocator-0-only) and [results documentation](docs/results.md).

They have **not** been remeasured as a complete five-size study under allocator `974848`.

## Launch the latest Mission Control GUI on the prepared Rover VM

**On the existing configured Rover VM only**, after the µD3TN node, contacts, Earth application and required dependencies have already been prepared:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This is the launcher used for the latest GUI demonstration. It invokes:

- `mission_control_v2_live_metrics.py` — live Mission Control GUI and measurements.
- `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py` — Rover CoAP/BPv7 engine.
- AAP2 Unix socket `/tmp/ud3tn-974848-rover.aap2.sock`.
- Live measurement outputs under `Results/raw/`, with result-generation scripts for charts and tables where sufficient observations exist.

The repository also provides the updated helper:

```bash
./scripts/rover_gui.sh
```

The helper now points to the same Experiment C launcher rather than the historical Rover GUI.

**Do not start a second GUI while one is running, and do not stop or restart GUI-managed µD3TN nodes just to run or inspect the GUI.**

The launcher locates the GUI and Rover engine relative to this repository and selects Python from `ROVER_GUI_PY`, the repository's `.venv`, a prepared laboratory virtual environment, or system `python3`. **It is not a one-command installer**: live experiments still require patched µD3TN, AAP2 sockets, forwarding contacts, compatible Python dependencies, and the Earth server.

The GUI starts with **NSTART=1**. Its experimental mode controls can change the effective limit to **NSTART=2** for a controlled aggregation test. This does **not** establish deployment-wide congestion-control safety.

## Reproduction and participant documentation

The following guides have been updated for the current IETF 127 setup:

| Guide | Purpose |
| --- | --- |
| [Installation guide](docs/installation.md) | Dependencies, patched µD3TN, Python environments and configuration |
| [Architecture](docs/architecture.md) | Rover–Satellite–Earth topology, addressing and communication |
| [IETF demonstration](docs/ietf-demo.md) | Demonstration workflow, Wireshark analysis and ON/OFF challenge |
| [Reproduction quick start](docs/reproduction.md) | Startup order, current ports, GUI launcher and participant checks |
| [Experimental results](docs/results.md) | Current allocator-974848 evidence and separately labeled historical measurements |

### Startup helpers

The current Hackathon branch includes these updated scripts:

| Script | Purpose |
| --- | --- |
| `scripts/start_ud3tn.sh` | Starts patched µD3TN with the selected Rover, Satellite or Earth allocator-974848 EID, port and AAP2 socket |
| `scripts/rover_contacts.sh` | Configures Rover forwarding contacts |
| `scripts/satellite_contacts.sh` | Configures Satellite forwarding contacts |
| `scripts/earth_contacts.sh` | Configures Earth forwarding contacts |
| `scripts/earth_server.sh` | Launches the allocator-974848 Earth CoAP server |
| `scripts/rover_gui.sh` | Launches Experiment C Mission Control v2 |
| `scripts/check_setup.sh` | Performs read-only local file and environment checks |

These scripts target the current laboratory configuration and require the patched software and local dependencies to be available.

**Important:** If the three-VM laboratory is already active, do not repeat daemon startup, contact registration or GUI startup. Reuse the running applications and follow the observation instructions in the demonstration guide.

The scripts alone do not establish that a fresh installation has been independently reproduced.

## Wireshark analysis

Packet inspection is an important part of the project.

The demonstrated workflow uses **Wireshark 4.6.9** with the available BPv7 decoding support and the project's experimental Lua dissector.

Useful files include:

- `wireshark/coapbp05_ipn64_PL65000.lua`
- `wireshark/wireshark-ipn-live.sh`
- `evidence/Earth_IPN974848_Single_and_Aggregate.pcapng`

On Earth, capture traffic on the internal interface:

```text
enp0s8
```

The current Earth TCPCLv3 port is:

```text
4773
```

Useful Wireshark display filters include:

```text
tcp.port == 4773
bpv7
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 2
```

Participants can examine:

- TCPCLv3 transport traffic between nodes.
- BPv7 Primary Blocks and bundle lifetimes.
- Source and destination EIDs.
- RFC 9758 three-component IPN encoding.
- Single and Aggregate CoAP application payloads.
- CoAP Message IDs and Tokens.
- Response correlation and delivery observations.

The live-capture helper can open Wireshark when the Flatpak build does not expose capture interfaces directly. It handles the host capture mechanism internally; participants do not need to launch `tcpdump` manually.

See the [Wireshark guide](wireshark/README.md) for setup details.

## Hackathon participant challenge — intermittent connectivity

The participant exercise investigates how direct CoAP over BPv7 behaves when the Rover–Satellite–Earth communication path is intermittently available.

### Scenario

A Rover collects scientific measurements and sends them to Earth through a Satellite.

During the mission, communication contacts can become unavailable.

Participants investigate whether BPv7 can preserve submitted data during an OFF interval and forward eligible bundles after connectivity returns.

### Tasks

1. Verify that the three-node testbed is prepared and that communication is working.
2. Send a Single CoAP request from Rover to Earth.
3. Inspect the corresponding BPv7 bundle and response in Wireshark.
4. Run a controlled two-request Science Aggregate and inspect its two CoAP members.
5. Introduce an OFF contact interval using the existing laboratory controls, with authorization from the lab owner.
6. Restore connectivity and investigate forwarding and return delivery.
7. Record timestamps, request and response Tokens, bundle lifetime, delivery results and any queueing delays.

Participants should distinguish **request submitted at Rover**, **request received at Earth**, and **response received at Rover**.

An OFF/ON scenario is an experimental challenge, **not an assertion that every delayed bundle will necessarily be delivered**.

## Protocol and experimental limitations

- CoAP over BPv7 is implemented experimentally using **direct AAP2-to-µD3TN** transport, not a UDP proxy.
- Requests use **NON CoAP** with a **24-bit MID** and distinct request Tokens. The demonstrated Aggregate contains **two member requests**; the receiver replies with separate Single messages.
- The modified aiocoap code currently uses a **prototype Payload-length option number `65000`**. This is **not** an assigned final draft option number, and its Critical/Unsafe properties must be addressed before standards-level interoperability claims.
- Experimental aggregation uses a **two-message buffer** and an approximately **10-second maximum aggregation delay** in the documented implementation.
- NSTART=2 is controlled experimental behavior; safe congestion control across multiple applications has **not** been demonstrated.
- Three-component IPN encoding requires the project-specific patched µD3TN and modified aiocoap sources; stock binaries should **not** be assumed compatible without validation.
- Contact schedules, clock synchronization, selected Python environments, local TCPCL ports and AAP2 registration settings are important.
- The prototype is **not production-hardened**.
- A complete end-to-end installation from a fresh checkout has **not been independently validated**.

## Repository guide

| Location | Purpose / status |
| --- | --- |
| [`gui-v2/IETF127_Experiment_C_Package/`](gui-v2/IETF127_Experiment_C_Package/) | **Current demonstrated Rover GUI, launcher and Experiment C engine** |
| [`experiments/Experiment_C_Updated_IPN974848/`](experiments/Experiment_C_Updated_IPN974848/) | Current allocator-974848 functional evidence and separate historical comparison |
| [`wireshark/`](wireshark/) | RFC 9758 inspection guidance, Lua CoAP-over-BPv7 decoder and live-capture helper |
| [`evidence/`](evidence/) | Saved packet captures and historical evidence; inspect filenames/configuration before comparing runs |
| [`Hackathon_Media/`](Hackathon_Media/) | Hackathon media and demonstration resources |
| [`vendor/aiocoap/`](vendor/aiocoap/) | Collected locally modified aiocoap source and upstream licensing information |
| [`patches/ud3tn/`](patches/ud3tn/) | Project patch for µD3TN, including IPN encoding support |
| [`applications/rover/`](applications/rover/) and [`applications/earth/`](applications/earth/) | Historical Rover application files and the current allocator-974848 Earth server alongside older Earth code. The working Rover engine is in the Experiment C GUI package |
| [`scripts/`](scripts/) | Updated µD3TN startup, Rover/Satellite/Earth contact scripts, Earth server launcher, Rover GUI launcher and setup checker for allocator 974848 and ports 4771–4773 |
| [`docs/`](docs/) | Updated installation, architecture, demonstration, reproduction and results documentation with historical experiments clearly identified |
| [`Results/`](Results/) | Collected run outputs, event records and result-processing scripts; empty files are not evidence of successful experiments |

**Important for participants:** The current IETF 127 startup scripts and demonstration guides use allocator `974848` and TCPCLv3 ports `4771–4773`.

Earlier experimental files using allocator `0` remain in the repository for historical reference and should not be mixed with the current configuration.

The current Experiment C GUI supports repository-relative paths and configurable Python environments. A complete end-to-end installation from a fresh checkout has **not yet been independently validated**.

**Do not restart or modify the running Rover, Satellite or Earth VM processes merely to follow the documentation.**

## Source provenance, licensing and safety

- The historical working laboratory reported µD3TN source revision `37b968d5742cbd75292b534f3421fac70acc46b7`. For independent participant installation, `scripts/prepare_participant_ud3tn.sh` clones the public [CoAPoverBP-no-proxy-version](https://github.com/ENTEL-WNG/CoAPoverBP-no-proxy-version) source at pinned revision `a2fb4311b89b31c30e93a5c1704f78131594e927`, checks/applies the project's nine-file three-component IPN patch, and attempts to build µD3TN. See [source provenance](docs/upstream-provenance.md). The fresh three-VM workflow has not yet been independently validated end to end.
- Vendored aiocoap components include their own upstream licenses. **Do not infer a license for the entire repository** without confirmation from the ENTEL-WNG maintainers.
- The laboratory previously reported an AAP2 configuration without a BDM secret. Use this setup **only on isolated, trusted lab networks** until security is properly reviewed.
- Do not publish credentials, VM images, authentication secrets or private runtime state. CoAP correlation Tokens in the protocol trace are **not account authentication tokens**.

## Project team

- **Mahitab Salah Elattar** — Remote Hackathon champion and lead developer of the IPN Draft-05 implementation · [mahitab.elattar@outlook.com](mailto:mahitab.elattar@outlook.com)
- **Prof. Anna Calveras** — Onsite Hackathon champion and research supervisor · [anna.calveras@upc.edu](mailto:anna.calveras@upc.edu)
- **Affiliation:** Universitat Politècnica de Catalunya (UPC), Wireless Networks Group (WNG)

**Acknowledgement:** We thank **Prof. Carles Gómez** for technical guidance, discussions and feedback. AI-assisted tools were used for documentation editing and some experiment-related development support; experimental claims are distinguished from independently verified results.

**Funding:** This work was funded in part by the Spanish **MCIU/AEI/10.13039/501100011033/FEDER/UE** through project **PID2023-146378NB-I00**.
