# Protocol architecture and laboratory topology — IETF 127, IPN allocator 974848

**Project:** Experimental direct CoAP over BPv7 using [draft-ietf-core-coap-bp-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05), RFC 9758 three-component `ipn:` EIDs, µD3TN/AAP2, and TCPCLv3. **No CoAP-to-UDP proxy is used.** This document describes the current IETF 127 laboratory configuration; it does not claim complete standards conformance or a validated clean-clone installation.

## 1. Current three-node topology

The laboratory uses three Ubuntu VirtualBox VMs joined by the internal `enp0s8` network. The NAT-facing `enp0s3` interface, when enabled, is not used as the BPv7 test path.

| Role | Internal VM IP (`enp0s8`) | µD3TN node EID | TCPCLv3 port | AAP2 Unix socket | Application service |
| --- | --- | --- | ---: | --- | --- |
| Rover | `192.168.100.3` | `ipn:974848.1.0` | `4771` | `/tmp/ud3tn-974848-rover.aap2.sock` | Safety `ipn:974848.1.10`; Science `ipn:974848.1.11` |
| Satellite | `192.168.100.2` | `ipn:974848.2.0` | `4772` | `/tmp/ud3tn-974848-sat.aap2.sock` | BPv7 forwarding relay; **no CoAP proxy** |
| Earth | `192.168.100.1` | `ipn:974848.3.0` | `4773` | `/tmp/ud3tn-974848-earth.aap2.sock` | CoAP server `ipn:974848.3.64` |

```text
  ROVER                          SATELLITE                          EARTH
  192.168.100.3                  192.168.100.2                      192.168.100.1
  ipn:974848.1.0                 ipn:974848.2.0                     ipn:974848.3.0
  TCPCLv3 :4771                  TCPCLv3 :4772                      TCPCLv3 :4773

  Safety ipn:974848.1.10 --\
                            +------> BPv7 forwarding -----------> CoAP server
  Science ipn:974848.1.11 -/                                  ipn:974848.3.64
            <------------------- separate BPv7 Single responses ----
```

**IPN form:** `ipn:allocator.node.service`. In this testbed, the allocator is `974848`; node numbers are Rover `1`, Satellite `2`, and Earth `3`. Service `0` identifies the node EID, whereas service `64` identifies the **Earth CoAP application**. These are different destinations: `ipn:974848.3.0` is not the same as `ipn:974848.3.64`.

Application URIs use the local `.ipn.alt` naming convention, resolved by the modified application implementation rather than public DNS:

- Safety GET: `coap://64.3.974848.ipn.alt/mission/safety-guidance`
- Science POST: `coap://64.3.974848.ipn.alt/science/observations`

Only three-component `ipn:` EIDs are within this implementation's scope; the `dtn:` scheme and a CoAP-to-UDP proxy are out of scope.

## 2. Components and forwarding path

1. **Rover:** The modified aiocoap code builds CoAP NON messages, and the Experiment C NodeA engine sends application data through AAP2 to the local patched µD3TN process. Safety and Science have separate AAP2 application registrations (`10` and `11`), with independent pending requests and aggregation state.
2. **Satellite:** µD3TN forwards BPv7 bundles via TCPCLv3 according to scheduled contacts; it does not decode requests in order to provide a CoAP proxy service.
3. **Earth:** The CoAP application registered as service `64` receives the BPv7 payload over AAP2, decodes Single requests or disaggregates Aggregate members, processes GET/POST requests, and sends **one separate Single NON response bundle per request**. Tokens correlate each response with its corresponding request.
4. **Return path:** Earth → Satellite → Rover, using BPv7 forwarding contacts. Observing a response sent on Earth does not alone establish that Rover has received and Token-matched it.

### Current application entry points

| Component | Current file or launcher |
| --- | --- |
| Rover GUI | `gui-v2/IETF127_Experiment_C_Package/mission_control_v2_live_metrics.py` |
| Rover GUI launcher | `gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh` |
| Rover engine | `gui-v2/IETF127_Experiment_C_Package/experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py` |
| Earth server | `applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py` |
| Earth launcher | `scripts/earth_server.sh` |
| µD3TN startup | `scripts/start_ud3tn.sh` |
| Contact configuration | `scripts/rover_contacts.sh`, `scripts/satellite_contacts.sh`, `scripts/earth_contacts.sh` |
| Wireshark Lua decoder | `wireshark/coapbp05_ipn64_PL65000.lua` |

The newer Rover GUI is launched on the **prepared Rover VM** with:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

The launcher uses machine-specific paths to a Python environment and assets; it is **not** a validated portable participant installer. The older `applications/rover/Rover_Mission_Control_Draft05_Aggregation.py` and `scripts/rover_gui.sh` remain historical entry points, not the current demonstrated GUI.

## 3. Contact scheduling and disruption experiments

Forwarding contacts are directional:

- Rover → Satellite, with reachability toward Earth.
- Satellite → Earth.
- Earth → Satellite, with reachability toward Rover.
- Satellite → Rover.

The updated GitHub contact scripts request **3,600-second (one-hour)** scheduled contacts with a `100000`-byte contact volume parameter. Those standard contacts are **not the same as the experimental ON/OFF challenge**. ON/OFF intervals may be introduced using authorized GUI contact controls and measured with time-stamped logs and `.pcapng` evidence; do not assume successful store-and-forward delivery or lifetime compliance without observing the result.

**Protect the live lab:** The latest Rover GUI may manage nodes and contacts. Never start duplicate µD3TN daemons, replace AAP2 sockets, force-kill GUI-managed processes or change live contact schedules merely to follow these instructions. The updated GitHub branch does not automatically update the running VM checkout.

## 4. Experimental CoAP framing and aggregation

- The current tests use **NON** requests and responses and a **24-bit CoAP Message ID** in the local experimental encoding.
- Each request has its own MID and Token. An experimental CoAP **Payload-length option (`65000`)** is used to delimit members in an Aggregate. That option number is **not a final assigned standards value**, and its option-bit properties require further review.
- **Single:** one CoAP message in a BPv7 application payload.
- **Aggregate:** two CoAP messages, from the **same Rover application EID** to the **same Earth CoAP EID**, encoded in one BPv7 application payload; Earth disaggregates both. The demonstrated response path uses two separate Single bundles, **not an Aggregate response**.
- The current GUI launcher begins with **NSTART=1**. A controlled GUI mode can raise the effective limit to **NSTART=2** for testing a two-request Aggregate. The documented engine has a two-message buffer and approximately 10-second maximum aggregation delay. This is **not** proof of safe congestion control across applications or deployments.

## 5. Evidence: current experiment versus historical experiment

The [current Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) documents specific allocator-`974848` tests:

| Observation in the documented run | BPv7 application payload | Evidence summary |
| --- | ---: | --- |
| Safety Single NON GET | **59 B** | **4/4** Token-matched `2.05 Content` responses |
| Science Single NON POST | **102 B** | **1/1** Token-matched `2.01 Created` response |
| Science two-member NON POST Aggregate | **212 B** | Two members with **50 B Payload-length** each; **2/2** Token-matched `2.01 Created` responses |

A current capture also demonstrates RFC 9758 three-element IPN EIDs with allocator `974848` and a documented BPv7 lifetime of **90,000 ms**. These are observations from particular runs, not fixed protocol sizes or a general reliability guarantee. A repository `.pcapng` is available at [`evidence/Earth_IPN974848_Single_and_Aggregate.pcapng`](../evidence/Earth_IPN974848_Single_and_Aggregate.pcapng); inspect its actual frames rather than assuming screenshot frame numbers match.

**Historical allocator-`0` experiments must not be mixed with the current run.** The older documentation reports a **116 B Safety Aggregate**, a **556 B Science Aggregate** with 227-byte member payloads, and ports `4671–4673`. Those observations belong to a different setup and are retained in [historical results](results.md).

On Earth, inspect TCPCLv3 traffic on TCP port **4773** using Wireshark 4.6.9, which can decode the three-element IPN EID fields; the project Lua dissector exposes experimental embedded CoAP members. See [Wireshark instructions](../wireshark/README.md) and the [Hackathon demo procedure](ietf-demo.md). Preserve `.pcapng` plus corresponding Rover/Earth logs when asserting response delivery.

## 6. Scope, limitations and reproduction

The implementation is a research prototype. Full Draft-05 conformance, standardized Payload-length encoding, cross-application congestion safety, security hardening, and clean-clone end-to-end reproduction have **not** been established. Patched µD3TN and modified aiocoap dependencies, VM-specific Python environments, state files, clock alignment and scheduled contacts remain important.

See the [installation guide](installation.md) for requirements and safeguards, the [IETF 127 demonstration guide](ietf-demo.md) for the step-by-step test, and the [Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) for current measurements and historical comparisons.

