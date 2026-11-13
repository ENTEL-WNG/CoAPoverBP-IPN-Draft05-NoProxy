# CoAP over BPv7 — Draft-05, three-component IPN, no proxy

**IETF 127 Hackathon research prototype** · [CoAP over BPv7 Internet-Draft (draft-ietf-core-coap-bp-05)](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/) · [RFC 9758: three-component IPN](https://www.rfc-editor.org/rfc/rfc9758) · [RFC 9171: BPv7](https://www.rfc-editor.org/rfc/rfc9171)

This repository contains an **experimental implementation of direct CoAP over Bundle Protocol Version 7 (BPv7)** for a Rover–Satellite–Earth delay/disruption-tolerant network. CoAP applications use a modified **aiocoap** implementation and **µD3TN/AAP2** to send CoAP messages in BPv7 bundles over TCPCLv3. **No CoAP-to-UDP proxy is used.** The laboratory implementation and packet dissector are research prototypes, not a claim of complete draft conformance.

> **Current lab configuration (13 November 2026):** RFC 9758 **three-component `ipn:` EIDs with allocator `974848`**, TCPCLv3 ports **4771–4773**, and the **Experiment C Mission Control v2** GUI. A later, allocator-974848 test demonstrated Single request/response exchanges and an Aggregate carrying two Science NON POST requests in one BPv7 payload, with separately matched Earth responses. Earlier allocator-`0` results are retained as **historical evidence**, not presented as measurements of the newer setup.

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

The addresses above correspond to **allocator.node.service**. The Earth CoAP application is `ipn:974848.3.64`, **not** the bare Earth node EID `ipn:974848.3.0`. The prototype uses **NON (non-confirmable) CoAP** requests. It does not use the `dtn:` endpoint scheme.

## Current functional evidence — allocator 974848

The updated [Experiment C package](experiments/Experiment_C_Updated_IPN974848/README.md) documents the later three-component IPN implementation and preserves screenshots and measurements separately from the original allocator-`0` payload-size study.

| Observed test | BPv7 application payload | Verified observation |
| --- | ---: | --- |
| Safety Single GET | **59 B** | **4/4** Token-matched `2.05 Content` responses in the documented test |
| Science Single POST | **102 B** | **1/1** Token-matched `2.01 Created` response |
| Science Aggregate | **212 B** | **Two NON POST requests in one BPv7 bundle**; **2/2** Token-matched `2.01 Created` responses |
| BPv7 Primary Block | — | Captured **90,000 ms** bundle lifetime in the documented trace |
| RFC 9758 EID encoding | — | Wireshark displayed **IPN Element Count = 3**, allocator **974848**, and the expected node/service numbers |

In the recorded Science Aggregate, each POST used a **50-byte Payload-length**, and the two member MIDs and Tokens were distinct. Earth parsed both CoAP requests and returned **two separate Single response bundles**. These results describe a **particular recorded test**, not a general reliability, performance or interoperability guarantee.

For Wireshark screenshots, per-test evidence and separation of historical/current datasets, see [Experiment C](experiments/Experiment_C_Updated_IPN974848/README.md). For capture instructions and the Lua dissector, see [Wireshark documentation](wireshark/README.md).

### Historical results — older allocator 0

Some older code examples, documents and captures use `ipn:0.*.*`, TCPCL ports `4671–4673`, and different payload sizes. For example, earlier Safety and Science Aggregates had **116 B** and **556 B** application payloads, respectively. These are **not the same run** as the 212 B Science Aggregate under allocator `974848`. Do **not** mix packet-frame numbers, Tokens, metrics or efficiency percentages from the two configurations.

The original experiment's payload-size efficiency numbers are preserved in [Experiment C's historical section](experiments/Experiment_C_Updated_IPN974848/README.md#4-historical-payload-size-comparison--allocator-0-only) and [earlier results notes](docs/results.md). They have **not** been remeasured as a complete five-size study under allocator `974848`.

## Launch the latest Mission Control GUI on the prepared Rover VM

**On the existing configured Rover VM only**, after the µD3TN node, contacts, Earth application and required dependencies have already been prepared:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This is the launcher used for the latest GUI demonstration. It invokes:

- `mission_control_v2_live_metrics.py` — live Mission Control GUI and measurements;
- `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py` — Rover CoAP/BPv7 engine;
- AAP2 Unix socket `/tmp/ud3tn-974848-rover.aap2.sock`;
- Live measurement outputs under `Results/raw/`, with result-generation scripts for charts/tables where sufficient observations exist.

**Do not start a second GUI while one is running, and do not stop/restart GUI-managed µD3TN nodes just to run or inspect the GUI.** The launcher has **machine-specific absolute paths**, including a particular Python virtual environment; this command is **not yet a validated one-command install for Hackathon participants on other systems**.

The GUI starts with **NSTART=1**. Its experimental mode controls can change the effective limit to **NSTART=2** for a controlled aggregation test. This does **not** establish deployment-wide congestion-control safety.

## Protocol and experimental limitations

- CoAP over BPv7 is implemented experimentally using **direct AAP2-to-µD3TN** transport, not a UDP proxy.
- Requests use **NON CoAP** with a **24-bit MID** and distinct request Tokens. The demonstrated Aggregate contains **two member requests**; the receiver replies with separate Single messages.
- The modified aiocoap code currently uses a **prototype Payload-length option number `65000`**. This is **not** an assigned final draft option number, and its Critical/Unsafe properties must be addressed before standards-level interoperability claims.
- Experimental aggregation uses a **two-message buffer** and an approximately **10-second maximum aggregation delay** in the documented implementation. NSTART=2 is controlled experimental behavior; safe congestion control across multiple applications has **not** been demonstrated.
- Three-component IPN encoding requires the project-specific patched µD3TN and modified aiocoap sources; stock binaries should **not** be assumed compatible without validation.
- Contact schedules, clock synchronization, the selected Python environments, local TCPCL ports and AAP2 registration settings are all important. This prototype is **not production-hardened**.

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
| [`applications/rover/`](applications/rover/) and [`applications/earth/`](applications/earth/) | **Older application entry points**; verify configuration before use |
| [`scripts/`](scripts/) | Mixed-generation helpers; some default scripts **still use allocator 0 / ports 4671–4673** and must **not** be used unchanged for allocator 974848 |
| [`docs/`](docs/) | Earlier installation, architecture, demo and results documentation; **some instructions still describe the older configuration** |
| [`Results/`](Results/) | Collected run outputs, event records and result-processing scripts; empty files are not evidence of successful experiments |

**Important for participants:** The newer `974848` GUI and evidence coexist with historical allocator-`0` scripts/documents. Until every launcher and guide has been reconciled, **do not follow the older `scripts/start_ud3tn.sh` or `docs/ietf-demo.md` commands blindly** for the current topology. This README identifies the validated current configuration but does **not** assert that a clean-clone end-to-end setup has been tested.

## Source provenance, licensing and safety

- The recorded original µD3TN laboratory source revision is `37b968d5742cbd75292b534f3421fac70acc46b7`; see [source provenance](docs/upstream-provenance.md). A matching upstream source remote and a reproducible clean-clone workflow still require confirmation.
- Vendored aiocoap components include their own upstream licenses. **Do not infer a license for the entire repository** without confirmation from the ENTEL-WNG maintainers.
- The laboratory previously reported an AAP2 configuration without a BDM secret. Use this setup **only on isolated, trusted lab networks** until security is properly reviewed.
- Do not publish credentials, VM images, authentication secrets or private runtime state. CoAP correlation Tokens in the protocol trace are **not account authentication tokens**.

## Project team

- **Mahitab Salah Elattar** — Remote Hackathon champion and lead developer of the IPN Draft-05 implementation · [mahitab.elattar@outlook.com](mailto:mahitab.elattar@outlook.com)
- **Prof. Anna Calveras** — Onsite Hackathon champion and research supervisor · [anna.calveras@upc.edu](mailto:anna.calveras@upc.edu)
- **Affiliation:** Universitat Politècnica de Catalunya (UPC), Wireless Networks Group (WNG)

**Acknowledgement:** We thank **Prof. Carles Gómez** for technical guidance, discussions and feedback. AI-assisted tools were used for documentation editing and some experiment-related development support; experimental claims are distinguished from independently verified results.

**Funding:** This work was funded in part by the Spanish **MCIU/AEI/10.13039/501100011033/FEDER/UE** through project **PID2023-146378NB-I00**.

