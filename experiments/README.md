# Experiments — CoAP over BPv7 with Three-Component IPN Addressing

This directory documents experimental evaluation of **direct CoAP over Bundle Protocol Version 7 (BPv7)** using **RFC 9758 three-component IPN endpoint identifiers**, µD3TN/AAP2, TCPCLv3, and a custom Wireshark CoAP-over-BPv7 Lua dissector. The current demonstration uses IPN allocator **974848**, not the earlier allocator **0**.

> **Evidence integrity:** The new allocator-974848 screenshots demonstrate successful Single and Aggregate exchanges. The original five-size aggregation-efficiency measurements in these packages were taken under **allocator 0** and are retained as **historical** results. Do not represent them as new allocator-974848 measurements or mix packet IDs, Tokens, or data from separate runs.

## Experiment packages currently in this folder

| Package | Purpose and contents |
| --- | --- |
| [Experiment A — Payload Size / IPN 974848](Experiment_A_Payload_Size_IPN974848/) | [README](Experiment_A_Payload_Size_IPN974848/README.md), revised report, updated Wireshark screenshots, current observations, legacy measurements and plots, verification script, live-capture helper, and original archived materials. |
| [Experiment C — Updated IPN 974848](Experiment_C_Updated_IPN974848/docs/experiments/experiment-c-payload-size/) | [README](Experiment_C_Updated_IPN974848/docs/experiments/experiment-c-payload-size/README.md), revised report, current Single/Aggregate and RFC 9758 screenshots, historical five-size sweep, calculations, figures, and archived original materials. |

**Repository layout note:** Experiment C was uploaded with an additional `docs/experiments/` directory inside `Experiment_C_Updated_IPN974848`; the link above points to its **actual GitHub path**. Both packages address payload size and aggregation efficiency, using overlapping historical data. No separate Experiment B directory is currently present.

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
- **Current capture:** Wireshark **4.6.9** on Earth, interface `enp0s8` via host `tcpdump` → FIFO when using the Flatpak installation.

## Verified recent observations

| Test | Packet/application evidence |
| --- | --- |
| Safety Single GET | 59-byte BP application payload, no Payload-length option, 100,000 ms requested lifetime; **4/4** matching `2.05 Content` responses. |
| Science Single POST | 102-byte BP application payload; **1/1** matching `2.01 Created` response. |
| Science Aggregate | **One BPv7 bundle**, **212-byte application payload**, **two NON POSTs**, each declaring **Payload-length = 50 B**; **2/2** independently matched `2.01 Created` responses. |
| Aggregate Primary Block | **90,000 ms** lifetime and valid CRC-16 shown in Wireshark. |
| RFC 9758 IPN | Both EIDs decoded with **IPN Element Count = 3** and **Allocator = 974848** (`ipn:974848.1.11` → `ipn:974848.3.64`). |

For the captured two-member Aggregate, the request MIDs were **2543436** and **2543437**, and the Tokens were `2f8ecb82` and `715deaac`. These identifiers apply to this **specific run**, not to every future experiment. The two responses were sent as **separate Single response bundles**.

**Latest screenshots:** [Experiment A](Experiment_A_Payload_Size_IPN974848/evidence/current_allocator974848/) · [Experiment C](Experiment_C_Updated_IPN974848/docs/experiments/experiment-c-payload-size/evidence/current_ipn974848/).

### Historical efficiency measurements (allocator 0)

The archived five-size sweep used 50, 100, 227, 500, and 1,000-byte POST payloads with the **older allocator-0/port-4673** setup. Its CSVs and charts are preserved, but its previously calculated byte-saving percentages **have not been revalidated** for allocator 974848. The new 212-byte Aggregate verifies functionality; by itself it **does not establish a new bandwidth-saving percentage**.

## Wireshark analysis

On the Earth VM, capture the Satellite–Earth TCPCLv3 connection on port **4773**. Wireshark **4.6.9** natively decodes the three-component IPN values; the repository's [experimental Lua dissector](../wireshark/coapbp05_ipn64_PL65000.lua) displays embedded CoAP Single/Aggregate messages, 24-bit MIDs, Tokens, and the local Payload-length option.

Useful **display filters** (one at a time):

```text
bpv7
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 2
tcp.port == 4773
```

If the protocol is not recognized automatically, use **Analyze → Decode As** for TCP port **4773 → TCPCL**. The Flatpak version of Wireshark cannot directly select host adapters; see [Experiment A's live-capture helper](Experiment_A_Payload_Size_IPN974848/scripts/wireshark_ipn974848_live.sh). **Do not stop or replace running GUI-managed µD3TN processes just to capture packets.** Ensure the three VMs are time-synchronized before starting; large clock differences previously caused `Lifetime Expired` bundle deletion.

## Recording additional experiments

For each future run, create a separate directory with:

1. A `README.md` describing its objective, date/time (with time zone), Git revision, patched µD3TN/aiocoap versions, VM EIDs/IPs, and contact schedule (including ON/OFF periods, if applicable).
2. Protocol settings: NON/Single/Aggregate, payload inputs, NSTART, buffer size, aggregation delay, bundle lifetime, and any network shaping.
3. Exact request/response MIDs and Tokens linked to the **same** run, delivery counts, queueing/RTT metrics, and clearly defined measured byte totals.
4. Raw `.pcapng` files **when available**, original Wireshark screenshots, validated CSV/JSONL and analysis scripts, and sanitized application logs.
5. Notes on anomalies, failed attempts, limitations, and the distinction between historical and current configurations.

Do not fabricate test results, commit VM images or credentials, or describe historical results as newly reproduced. Congestion safety for **NSTART=2**, interoperability, and the experimental **Payload-length option 65000** require further standards-oriented validation.

## Related documentation

- [Installation guide](../docs/installation.md) and [IETF demonstration guide](../docs/ietf-demo.md) (some older sections describe allocator 0; prefer each updated experiment README for the current profile).
- [Results documentation](../docs/results.md).
- [CoAP over BPv7 Draft-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/), [RFC 9171](https://www.rfc-editor.org/rfc/rfc9171), and [RFC 9758](https://www.rfc-editor.org/rfc/rfc9758).

**Acknowledgement:** AI tools assisted in editing and organizing documentation. Protocol and experimental claims are based on the referenced captures, application logs, and preserved datasets.
