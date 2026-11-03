# CoAP over BPv7 — Three-component IPN, Draft-05, no proxy

**Research prototype** · [IETF CoAP-over-BP draft-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp/05/) · [Reproduce the IETF demo](docs/ietf-demo.md)

This repository records an **experimental, direct CoAP-over-BPv7 implementation** developed for the ENTEL/WNG research testbed. CoAP applications communicate through µD3TN and AAP2, **without a CoAP-to-UDP proxy**. The implementation uses RFC 9758-style three-component IPN endpoint identifiers, a modified aiocoap serializer, and a custom Wireshark Lua dissector.

> **Status (2 November 2026):** Safety GET and Science POST **Single and Aggregate request exchanges were demonstrated** in the three-VM lab. This is **not** a claim of full draft-05 conformance, production security, congestion safety, or successful installation from a clean clone. In the tested path, Earth disaggregates Aggregate requests and returns **separate Single response bundles**.

## Architecture

```text
ROVER (192.168.100.3)           SATELLITE (192.168.100.2)          EARTH (192.168.100.1)
µD3TN ipn:0.1.0 :4671          µD3TN ipn:0.2.0 :4672            µD3TN ipn:0.3.0 :4673
  Safety  ipn:0.1.10  -------\                                     /-->  CoAP server ipn:0.3.64
  Science ipn:0.1.11  --------> BPv7 / TCPCLv3 relay  ----------/     GET  /mission/safety-guidance
                                                                    POST /science/observations
          <---------------------- two individual Single responses ---
```

- Rover CoAP authority: `64.3.0.ipn.alt`, mapping to the **CoAP application** endpoint `ipn:0.3.64` (not to the bare Earth node `ipn:0.3.0`). The `.ipn.alt` host is an application-level non-DNS naming convention.
- Two distinct Rover AAP2 application registrations: **Safety** service 10 and **Science** service 11. Their aggregation buffers and pending-request state are separate.
- Satellite is a **BP relay**, not a CoAP proxy.
- Three VMs use VirtualBox internal interface `enp0s8` and the above fixed IPs. Contact schedules are supplied by AAP2 and expire after one hour.

See [architecture](docs/architecture.md) for the node table and [installation](docs/installation.md) for dependencies and daemon commands.

## Evidence from the verified runs

| Test | Incoming BPv7 application payload on Earth | Earth application result |
| --- | ---: | --- |
| Safety Aggregate | **116 B** | 2 NON GET requests parsed; 2 independent `2.05 Content` responses |
| Science Aggregate | **556 B** | 2 NON POST requests parsed; 2 independent `2.01 Created` responses |
| Science request/response capture | Frame **14** Aggregate; frames **31, 49** separate responses | Request Tokens **`9fc152cf`**, **`5ae01fab`** match corresponding response Tokens |

Science Aggregate frame 14 contains request 24-bit MIDs **4858056** and **4858057** and per-member **Payload-length = 227**. The custom Wireshark decoder displays both members directly beneath BPv7. The Safety Aggregate has **Payload-length = 3** per GET. Rover terminal logs separately demonstrated successful request/response Token matching and `Pending: 0` in earlier runs. **Do not conflate those earlier console-run MIDs with the later Wireshark-captured Science run.** See [experimental results](docs/results.md).

### Experimental protocol choices and limitations

- **24-bit CoAP Message ID**, distinct MID and 4-byte Token per request.
- Experimental CoAP **Payload-length option number 65000** in the local aiocoap fork. It is **not an assigned final draft option number**, and its option-bit semantics need review before standards claims.
- Controlled experimental **NSTART = 2 per Rover application**; buffer limit **2 messages** and maximum aggregation delay **10 seconds**. **Cross-application congestion control is not established.**
- In the observed path, two requests share **one BPv7 payload**, but the two responses use **two separate BPv7 bundles**; response aggregation remains future work.
- The current no-proxy implementation and decoder are an experiment-specific wire format; interoperability and full draft-05 compliance need additional tests.

## Repository map

| Directory | Contents |
| --- | --- |
| `applications/rover/` | Draft-05 CoAP client/aggregation engine and Mars Rover GUI |
| `applications/earth/` | Draft-05 Earth CoAP application server |
| `vendor/aiocoap/` | Collected modified aiocoap source, setup metadata and upstream licenses |
| `patches/ud3tn/` | Validated nine-file IPN/CBOR/AAP2 patch against the recorded source snapshot |
| `wireshark/` | Lua BPv7→CoAP decoder for IPN services 10/11/64 |
| `scripts/` | Three-node daemon launch, contact configuration and app run scripts |
| `evidence/safety/`, `evidence/science/` | Original saved packet captures from Earth |
| `docs/` | Installation, protocol architecture, results, demo and source provenance |
| `experiments/` | Instructions for documenting new runs |

## Start here

**Already have the verified three VirtualBox VMs?** Read the [existing-lab steps](docs/installation.md#route-a-reuse-the-existing-tested-three-vm-lab) and follow the [IETF demonstration](docs/ietf-demo.md). The shell scripts intentionally take their µD3TN checkout and Python environment locations from configurable environment variables, falling back to the known lab locations.

**Starting from a new checkout?** Read the [fresh-environment prerequisites and limitations](docs/installation.md#route-b-prepare-an-independent-checkout-not-yet-validated). The µD3TN source is distributed as a **patch**, not a complete upstream checkout. You must obtain the corresponding original source tree at Git commit `37b968d5742cbd75292b534f3421fac70acc46b7`, apply the patch, build it and confirm the environment dependencies. The source remote for that commit still needs to be recorded.

```bash
# On each test VM after cloning this private repository:
./scripts/check_setup.sh
# Start daemon, contacts and app according to docs/ietf-demo.md
```

## Provenance, licensing and security

- Original laboratory source revision: **`37b968d5742cbd75292b534f3421fac70acc46b7`**. The nine-file µD3TN patch was checked both against the base Git index and in reverse against the modified live working tree. See [provenance](docs/upstream-provenance.md).
- Modified aiocoap is redistributed with its `MIT` and `BSD-3-Clause` license texts. Do not infer a license for the *entire project* from those vendored licenses; confirm the project license with the ENTEL-WNG maintainers.
- The testbed previously warned that its AAP2 interface had **no configured BDM secret**. Treat it as an **isolated, trusted lab only**. Do not expose these defaults on public networks.
- Packet captures contain testbed IPs and application data. Do not commit credentials, tokens used for authentication, VM images, local runtime state or private logs. CoAP correlation Tokens shown in traces are **not GitHub authentication tokens**.

## AUTHORS
**Mahitab Salah Elattar** — Lead developer of the IPN Draft-05 implementation
**Anna Calveras** ([anna.calveras@upc.edu](mailto:anna.calveras@upc.edu)) — Project supervisor

## Acknowledgements
We would like to thank **Carles Gómez** for his valuable guidance, technical discussions, and feedback on this research work.

## Funding
This work is partially supported by Spanish MCIN/AEI/10.13039/501100011033/FEDER/UE through project **PID2023-146378NB-I00**.
