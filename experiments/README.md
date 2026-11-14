
# Experiments — CoAP over BPv7 with Three-Component IPN Addressing

This directory documents experimental evaluation of **direct CoAP over Bundle Protocol Version 7 (BPv7)** using **RFC 9758 three-component IPN endpoint identifiers**, µD3TN/AAP2, TCPCLv3, and a custom Wireshark CoAP-over-BPv7 Lua dissector.

The current IETF 127 Hackathon demonstration uses IPN allocator **974848**, not the earlier allocator **0**.

> **Evidence integrity:** The allocator-974848 screenshots demonstrate successful Single and Aggregate exchanges. The original five-size aggregation-efficiency measurements were collected under **allocator 0** and are retained as **historical results**. Do not represent them as new allocator-974848 measurements or combine packet IDs, Tokens, or data from separate runs.

## Experiment packages currently in this folder

| Package | Purpose and contents |
| --- | --- |
| [Experiment A — Payload Size / IPN 974848](Experiment_A_Payload_Size_IPN974848/) | [README](Experiment_A_Payload_Size_IPN974848/README.md), revised report, updated Wireshark screenshots, current observations, legacy measurements and plots, verification script, live-capture helper, and archived materials. |
| [Experiment C — Updated IPN 974848](Experiment_C_Updated_IPN974848/) | [README](Experiment_C_Updated_IPN974848/README.md), revised report, current Single/Aggregate and RFC 9758 screenshots, historical five-size sweep, calculations, figures, and archived original materials. |

**Repository layout note:** Experiment C's current README and supporting materials are directly inside `Experiment_C_Updated_IPN974848/`. Experiment A and Experiment C contain overlapping historical payload-size data, which must remain separate from the latest allocator-974848 functional evidence.

No separate Experiment B directory is currently present.

## Current verified testbed

| Component | Internal address | Three-component IPN EID | TCPCLv3 |
| --- | --- | --- | --- |
| Rover node | `192.168.100.3` | `ipn:974848.1.0` | `4771` |
| Rover Safety app | Rover AAP2 | `ipn:974848.1.10` | Via Rover node |
| Rover Science app | Rover AAP2 | `ipn:974848.1.11` | Via Rover node |
| Satellite relay | `192.168.100.2` | `ipn:974848.2.0` | `4772` |
| Earth node | `192.168.100.1` | `ipn:974848.3.0` | `4773` |
| Earth CoAP server | Earth AAP2 | `ipn:974848.3.64` | Via Earth node |

- **Architecture:** Rover → Satellite → Earth; the Satellite is a **BPv7 relay**, not a CoAP proxy.
- **Protocol scope:** CoAP NON requests, direct CoAP/BPv7, three-element IPN EID encoding.
- **Science URI:** `coap://64.3.974848.ipn.alt/science/observations`.
- **Safety URI:** `coap://64.3.974848.ipn.alt/mission/safety-guidance`.
- **Current capture:** Wireshark **4.6.9** on Earth, interface `enp0s8`, using host `tcpdump` → FIFO when running Wireshark through Flatpak.

## Verified recent observations

The current allocator-974848 implementation has been tested with Safety and Science CoAP applications communicating with Earth through the Satellite BPv7 relay.

| Test | Packet/application evidence |
| --- | --- |
| Safety Single GET | 59-byte BP application payload, no Payload-length option, 100,000 ms requested lifetime; **4/4** matching `2.05 Content` responses. |
| Science Single POST | 102-byte BP application payload; **1/1** matching `2.01 Created` response. |
| Science Aggregate | **One BPv7 bundle**, **212-byte application payload**, **two NON POSTs**, each declaring **Payload-length = 50 B**; **2/2** independently matched `2.01 Created` responses. |
| Aggregate Primary Block | **90,000 ms** lifetime and valid CRC-16 shown in Wireshark. |
| RFC 9758 IPN | Source and destination EIDs decoded with **IPN Element Count = 3** and **Allocator = 974848** (`ipn:974848.1.11` → `ipn:974848.3.64`). |

### Science Aggregate — recorded evidence

The recorded Science Aggregate contained two NON POST requests in one BPv7 application payload.

| Field | First CoAP request | Second CoAP request |
| --- | --- | --- |
| Method | NON POST | NON POST |
| Source application | `ipn:974848.1.11` | `ipn:974848.1.11` |
| Destination application | `ipn:974848.3.64` | `ipn:974848.3.64` |
| MID | `2543436` | `2543437` |
| Token | `2f8ecb82` | `715deaac` |
| Payload-length | 50 B | 50 B |
| Recorded response | `2.01 Created` | `2.01 Created` |

The complete Aggregate had a recorded **212-byte BPv7 application payload**.

Earth decoded both CoAP requests and generated two separate Single response bundles, each correlated using its request Token.

These identifiers and payload sizes apply to this **specific recorded run**, not to every future experiment.

### Current experiment screenshots

- [Experiment A — allocator 974848 screenshots](Experiment_A_Payload_Size_IPN974848/evidence/current_allocator974848/)
- [Experiment C — allocator 974848 screenshots](Experiment_C_Updated_IPN974848/evidence/current_ipn974848/)
- [Experiment C — complete report](Experiment_C_Updated_IPN974848/README.md)

## Historical efficiency measurements — allocator 0

The archived five-size sweep used the following POST payload sizes:

- 50 bytes
- 100 bytes
- 227 bytes
- 500 bytes
- 1,000 bytes

These experiments used the **older allocator-0 configuration**, including Earth TCPCL port `4673`.

The historical byte-saving measurements were:

| Application payload size | Two Singles (reconstructed TCP bytes) | Aggregate (reconstructed TCP bytes) | Reduction |
| ---: | ---: | ---: | ---: |
| 50 B | 292 | 251 | 14.04% |
| 100 B | 392 | 352 | 10.20% |
| 227 B | 648 | 606 | 6.48% |
| 500 B | 1194 | 1154 | 3.35% |
| 1000 B | 2194 | 2154 | 1.82% |

These percentages describe the preserved historical observations and have **not been revalidated under allocator 974848**.

The new 212-byte Science Aggregate verifies functionality, but it does **not by itself establish a new bandwidth-saving percentage**.

Older Safety and Science Aggregate tests also recorded **116-byte** and **556-byte** BP application payloads, respectively. These values should not be mixed with the current 212-byte Science Aggregate.

## Wireshark analysis

Wireshark inspection is an important part of the experimental evidence.

On the Earth VM, capture the Satellite–Earth TCPCLv3 connection on port **4773**.

Wireshark **4.6.9** natively decodes the RFC 9758 three-component IPN values.

The repository's experimental Lua dissector provides embedded CoAP decoding:

[`wireshark/coapbp05_ipn64_PL65000.lua`](../wireshark/coapbp05_ipn64_PL65000.lua)

The dissector can display:

- Single and Aggregate CoAP messages.
- CoAP NON message type and request/response codes.
- 24-bit CoAP Message IDs.
- CoAP Tokens.
- Experimental Payload-length option 65000.
- The two embedded CoAP messages in a demonstrated Aggregate.

### Recommended Wireshark display filters

Use the following filters individually:

```text
bpv7
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 2
tcp.port == 4773
```

If the protocol is not recognized automatically, use **Analyze → Decode As** for TCP port **4773 → TCPCL**.

### Live capture

When native Wireshark exposes the Earth VM network interface, select:

```text
enp0s8
```

When using the Wireshark Flatpak installation without directly visible capture interfaces, use the project's live-capture helper:

```bash
bash wireshark/wireshark-ipn-live.sh enp0s8
```

The helper internally captures host traffic and streams it to Wireshark.

Participants do not need to launch a separate `tcpdump` command.

For additional instructions, see the [Wireshark guide](../wireshark/README.md).

**Important:** Do not stop or replace running GUI-managed µD3TN processes just to capture packets. Ensure the three VMs are time-synchronized before starting experiments; large clock differences previously caused `Lifetime Expired` bundle deletion.

## Recording additional experiments

For each future experiment, create a separate directory containing:

1. A `README.md` describing its objective, date/time with time zone, Git revision, patched µD3TN and aiocoap versions, VM EIDs/IPs, and contact schedule including ON/OFF periods when applicable.
2. Protocol settings, including NON, Single or Aggregate mode, payload inputs, NSTART, buffer size, aggregation delay, bundle lifetime, and any network shaping.
3. Exact request/response MIDs and Tokens linked to the **same run**, delivery counts, queueing/RTT metrics, and clearly defined measured byte totals.
4. Raw `.pcapng` files **when available**, original Wireshark screenshots, validated CSV/JSONL files, analysis scripts and sanitized application logs.
5. Notes on anomalies, failed attempts, limitations, and the distinction between historical and current configurations.

### Evidence requirements

Future experimental reports should distinguish:

- **Submission:** The request was generated or submitted on Rover.
- **Reception:** The request bundle reached Earth and the CoAP application processed it.
- **Response delivery:** The corresponding response reached Rover and was matched to the original request Token.

Do not assume successful end-to-end delivery from a local sender message alone.

Do not fabricate experimental results, commit VM images or credentials, or describe historical results as newly reproduced.

Congestion safety for **NSTART=2**, interoperability, and the experimental **Payload-length option 65000** require further standards-oriented validation.

## Related documentation

- [Main project README](../README.md)
- [Installation guide](../docs/installation.md)
- [Architecture](../docs/architecture.md)
- [IETF demonstration guide](../docs/ietf-demo.md)
- [Reproduction quick start](../docs/reproduction.md)
- [Results documentation](../docs/results.md)
- [Wireshark guide](../wireshark/README.md)
- [CoAP over BPv7 Draft-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/)
- [RFC 9171 — Bundle Protocol Version 7](https://www.rfc-editor.org/rfc/rfc9171)
- [RFC 9758 — IPN EID Scheme](https://www.rfc-editor.org/rfc/rfc9758)

## Acknowledgement

AI-assisted tools were used to help edit and organize the experiment documentation.

Protocol and experimental claims are based on the referenced captures, application logs, and preserved datasets.

**Project:** CoAP over BPv7 with Three-Component IPN Addressing and Message Aggregation  
**Affiliation:** Universitat Politècnica de Catalunya (UPC), Wireless Networks Group (WNG)  
**Hackathon:** IETF 127
