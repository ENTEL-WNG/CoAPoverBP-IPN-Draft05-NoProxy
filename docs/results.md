# Experimental results — IETF 127, CoAP over BPv7 with three-component IPN

**Project:** Experimental direct CoAP over BPv7 (draft-ietf-core-coap-bp-05), patched µD3TN/AAP2 and modified aiocoap, **without a CoAP-to-UDP proxy**.

> **Important: two different test configurations.** The current IETF 127 laboratory uses RFC 9758 three-component `ipn:` endpoint IDs with allocator **`974848`** and TCPCLv3 ports **`4771–4773`**. Earlier experiments used allocator **`0`** and ports **`4671–4673`**. Their payload sizes, Message IDs, Tokens, Wireshark frame numbers and performance measurements must **not be mixed**. Results below are observations from documented tests, not a statement of general reliability or full Draft-05 compliance.

## 1. Current laboratory configuration — allocator 974848

| Node | Internal IP (`enp0s8`) | Node EID | TCPCLv3 port | CoAP application EID |
| --- | --- | --- | ---: | --- |
| Rover | `192.168.100.3` | `ipn:974848.1.0` | `4771` | Safety `ipn:974848.1.10`; Science `ipn:974848.1.11` |
| Satellite | `192.168.100.2` | `ipn:974848.2.0` | `4772` | BPv7 forwarding only; no CoAP proxy |
| Earth | `192.168.100.1` | `ipn:974848.3.0` | `4773` | CoAP server `ipn:974848.3.64` |

The current Rover application uses the **Experiment C Mission Control v2** launcher at `gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh` and its corresponding NodeA engine. The updated Earth server is `applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py`. Requests are CoAP NON; Earth returns separate Single response bundles. See [architecture](architecture.md), [installation](installation.md), and the [IETF demo guide](ietf-demo.md).

## 2. Documented functional results — allocator 974848

The [updated Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) records these observations:

| Test | BPv7 application payload | Request details | Documented response outcome |
| --- | ---: | --- | --- |
| Safety **Single** GET | **59 B** | One NON `GET /mission/safety-guidance`; Payload-length absent | **4/4** Token-matched `2.05 Content` responses in the documented test |
| Science **Single** POST | **102 B** | One NON `POST /science/observations` | **1/1** Token-matched `2.01 Created` response |
| Science **Aggregate** | **212 B** | **Two NON POST requests in one BPv7 application payload**, each carrying Payload-length **50 B** | **2/2** Token-matched `2.01 Created` responses; Earth sent separate Single responses |

For the documented Science Aggregate, the two request MIDs were **`2543436`** and **`2543437`**; Tokens were **`2f8ecb82`** and **`715deaac`**. These identify that particular run and will change in subsequent tests. The results are **not** evidence that every pair of GUI button clicks is automatically aggregated: the experimental mode, outstanding-request limits and buffer timing must permit it.

### Current Wireshark evidence

The updated Experiment C evidence records:

- Wireshark **4.6.9** displaying RFC 9758 three-component IPN source and destination identifiers: **IPN Element Count = 3**, allocator **`974848`**, source Science service `11`, Earth destination service `64`.
- A Science Aggregate with **two CoAP POST members in one 212-byte BPv7 application payload**, with independent MIDs and Tokens and a **50-byte Payload-length** for each member.
- A BPv7 Primary Block lifetime of **90,000 ms** and good CRC-16 in **frame 76** of the screenshot-documented capture. The original Safety Single test separately recorded a requested lifetime of **100,000 ms**; do not treat these as identical observations.

Current screenshots are in [`experiments/Experiment_C_Updated_IPN974848/evidence/current_ipn974848/`](../experiments/Experiment_C_Updated_IPN974848/evidence/current_ipn974848/). The repository also contains [`evidence/Earth_IPN974848_Single_and_Aggregate.pcapng`](../evidence/Earth_IPN974848_Single_and_Aggregate.pcapng). **Do not assume frame 76, or the screenshot MIDs, occur at the same locations in this separate `.pcapng` file without inspecting it.**

In Wireshark on Earth, inspect `enp0s8`, TCPCLv3 **port `4773`**, and use display filters such as `bpv7`, `bpv7.eid.ipn_count == 3`, `bpv7.eid.ipn_alloc == 974848`, and `coapbp05.count == 2` (the last requires the repository's experimental Lua dissector). See [Wireshark instructions](../wireshark/README.md).

## 3. Historical results — allocator 0 only

**These results predate the allocator-974848 configuration.** Their EIDs used `ipn:0.*.*` and TCPCLv3 ports `4671–4673`. Preserve them as historical experiments, not current Hackathon results.

### Safety Aggregate: CoAP NON GET

- Source/destination: `ipn:0.1.10` → `ipn:0.3.64`.
- Two Safety GET messages in **one 116-byte BPv7 application payload**.
- Independent MIDs and Tokens; Payload-length **3** for each request member.
- Earth sent two separate Single NON `2.05 Content` responses. Rover logs from the documented console run reported both response Tokens matched, with pending requests returning to zero.
- Example request pair: MID **`12410189`**, Token **`d7ef6f92`**; MID **`12410190`**, Token **`3fda244f`**.

### Science Aggregate: CoAP NON POST

- Source/destination: `ipn:0.1.11` → `ipn:0.3.64`.
- Two Science POST messages in **one 556-byte BPv7 application payload**; Payload-length **227 B** per member.
- An **earlier console test** reported request MIDs **`4858053`** and **`4858054`**, with matched Rover responses.
- A **different Wireshark-captured test** reported request frame **14**, MIDs **`4858056`** and **`4858057`**, Tokens **`9fc152cf`** and **`5ae01fab`**. Response frames **31** and **49** carried separate **54-byte** BPv7 application payloads, corresponding Tokens and CoAP `2.01 Created` codes.

**Do not combine** the console-run MIDs with the captured-run frame numbers, and do not claim Rover received responses for a particular capture unless corresponding Rover logs from that same run show Token matching.

### Historical payload-size comparison

The original Experiment C report records request-direction reconstructed TCP bytes for two Singles compared with one Aggregate under allocator `0`:

| JSON payload per POST | Two Singles TCP bytes | Aggregate TCP bytes | Historical saving |
| ---: | ---: | ---: | ---: |
| 50 B | 292 B | 251 B | 14.04% |
| 100 B | 392 B | 352 B | 10.20% |
| 227 B | 648 B | 606 B | 6.48% |
| 500 B | 1,194 B | 1,154 B | 3.35% |
| 1,000 B | 2,194 B | 2,154 B | 1.82% |

These are **historical reconstructed TCP-byte comparisons**, not Ethernet on-wire sizes, and the 227-byte observation came from an earlier live workload. The full historical methodology, CSV and archive are described in [Experiment C](../experiments/Experiment_C_Updated_IPN974848/README.md#4-historical-payload-size-comparison--allocator-0-only). **The complete five-size comparison has not been repeated under allocator `974848`**, so do not transfer these savings percentages to the current demonstration.

## 4. Interpretation, limitations and next experiments

- **Single versus Aggregate:** A Single contains one CoAP message in a BPv7 application payload. The documented Science Aggregate combines **two requests in one payload**, but Earth returns **two independent Single response bundles**; response aggregation has not been demonstrated.
- **NSTART:** The updated GUI starts with **NSTART=1**. A controlled experimental GUI mode can use **NSTART=2**, with a two-message aggregation buffer and approximately 10-second maximum wait. This is **not evidence of safe cross-application congestion control**.
- **Experimental encoding:** The modified CoAP-over-BPv7 format uses a **24-bit MID** and a prototype **Payload-length option number `65000`**. That number is not a final standards assignment; its Critical/Unsafe option semantics and interoperability require further review.
- **Evidence boundaries:** Submission to local µD3TN is not proof of arrival at Earth. A server-sent response is not proof Rover received it. Correlate `.pcapng` captures with Rover/Earth logs from **the same run** and verify matching Tokens.
- **Reproducibility:** A fully independent clean-clone end-to-end setup has not been validated. The existing prepared three-VM lab depends on patched µD3TN, modified aiocoap, specific AAP2 sockets and installed Python environments. Do **not** restart GUI-managed nodes or overwrite a working VM merely to reproduce a trace.
- **Next experiments:** Repeat the payload-size sweep under allocator `974848`; compare Single (`NSTART=1`) and controlled Aggregate (`NSTART=2`) modes with identical payloads; record serialized BP/TCP bytes, response latency, contact ON/OFF periods, queueing delay, losses and bundle lifetime. Treat successful store-and-forward delivery during outages as a hypothesis to test, not an outcome already proven by these results.

**Supporting files:** [Current Experiment C](../experiments/Experiment_C_Updated_IPN974848/README.md) · [Wireshark](../wireshark/README.md) · [IETF 127 demo](ietf-demo.md) · [Current capture](../evidence/Earth_IPN974848_Single_and_Aggregate.pcapng).
