# Experiment C: Payload Size Versus Aggregation Efficiency

**Project:** CoAP over BPv7 with RFC 9758 IPN addressing and CoAP message aggregation  
**Report type:** Experimental results — First finding  
**Date of observations:** 7–8 November 2026  
**Prepared for:** UPC Wireless Networks Group / IETF 127 Hackathon  
**Specification baseline:** [draft-ietf-core-coap-bp-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp/05/) (28 October 2026)  
**Status:** First-round exploratory measurements; not yet a congestion-control safety study

## Executive summary

We evaluated the effect of **CoAP application-payload size** on request-side serialization efficiency when sending **two NON POST requests** either as (a) two independent BPv7 Singles with **NSTART=1**, or (b) one BPv7 Aggregate containing two CoAP members with **NSTART=2**. The three-VM Rover → Satellite → Earth topology used continuously connected TCPCLv3 links, without a CoAP proxy. Message contents for four fixed benchmark sizes were generated beforehand and reused in each comparison.

**Main result.** The measured request-side reassembled TCP data decreased by **40–42 bytes per request pair** when one Aggregate replaced two Singles. The relative reduction was **14.04% at 50 B**, **10.20% at 100 B**, **6.48% at 227 B**, **3.35% at 500 B**, and **1.82% at 1,000 B**. The 227 B row comes from a separate earlier Science workload and is included as contextual corroboration rather than a fixed-file control.

**Interpretation.** Eliminating one set of BPv7/TCPCL serialization metadata saves approximately one envelope. The Aggregate incurs additional CoAP Payload-length option bytes. Therefore, the **absolute** byte saving is relatively stable while the **relative** saving falls as payload size grows. This is a measured result for **request-side serialized TCP bytes only**, **not** a measured reduction in all on-wire Ethernet bytes, network utilization, or congestion.

![Relative saving](figures/relative_savings.png)

## 1. Research question and hypothesis

**Question:** For two CoAP NON Science POSTs destined for the same endpoint, how does application-payload size change the serialization-byte benefit of application-layer aggregation over BPv7?

**Hypothesis H1:** When aggregating two otherwise equivalent CoAP messages, the additional option encoding costs a relatively small number of bytes and one BPv7/TCPCL envelope is avoided. The **percentage** request-byte reduction should be greater for smaller application messages, even when the **absolute** reduction remains similar.

**Not tested by H1:** congestion safety of NSTART=2, performance under sustained load, end-to-end delay improvement, delivery probability, and physical-link byte counts.

## 2. System and implementation context

| Property | Configuration |
|---|---|
| Topology | Rover → Satellite (BP relay) → Earth, with return bundles via Satellite |
| Links | Continuously connected internal VirtualBox links (`enp0s8`); no induced ON/OFF outages |
| Rover node | `192.168.100.3`, `ipn:0.1.0`, TCPCLv3 port `4671` |
| Satellite node | `192.168.100.2`, `ipn:0.2.0`, TCPCLv3 port `4672` |
| Earth node | `192.168.100.1`, `ipn:0.3.0`, TCPCLv3 port `4673` |
| CoAP client | Rover Science `ipn:0.1.11` (Wireshark may display `ipn:1.11`) |
| CoAP destination | Earth service `ipn:0.3.64` (Wireshark may display `ipn:3.64`) |
| URI | `coap://64.3.0.ipn.alt/science/observations` |
| CoAP request | NON POST, 24-bit MID, 4-byte Token; distinct MID/Token per request |
| Responses | Two independent NON `2.01 Created` response messages |
| Runtime | Existing µD3TN BPv7 daemon, AAP2, experimental Rover GUI and Earth NodeB |
| Controls | Single: NSTART=1; Aggregate: NSTART=2, maximum two members, 10 s aggregation timer |
| Bundle lifetime requested | 100 s for NON Single; 90 s for NON Aggregate in this implementation |

**EID notation:** The configured identifiers are written as `ipn:0.node.service` (RFC 9758). When allocator 0 is elided, a Wireshark display like `ipn:1.11` denotes the same three-component logical endpoint. This display distinction does not imply a different node.

### Relevant standards

- **Draft-05 §4.2:** CoAP-over-BP Single uses a 24-bit Message ID.
- **Draft-05 §4.3:** The Payload-length option **must not** appear in a BP-encapsulated Single; it identifies member payload boundaries in an Aggregate.
- **Draft-05 §6:** NSTART defaults to 1. A larger value requires deployment-specific congestion-control safety, and the number of outstanding Single messages in an Aggregate is bounded by NSTART.
- **RFC 9758:** Three logical IPN components (allocator, node, service); display or CBOR compact forms may vary.
- **RFC 7252 §3.1:** CoAP options use differential option numbering and variable-length value encoding.

**Prototype interoperability caveat:** The experimental implementation uses local Payload-length option number **65000** while Draft-05 still specifies **TBD1**. The draft requires the option to be critical and unsafe-to-forward. Under RFC 7252's option-bit conventions, number 65000 is not marked critical/unsafe. These results therefore document **prototype behavior**, not final standards compliance of the option-number assignment; this requires revision before a full conformance claim.

## 3. Experimental method

1. Create two deterministic JSON Science observations for each requested application size (**50, 100, 227, 500, 1,000 bytes**) and save files with distinct IDs. The controlled size is the **entire JSON byte string**, not just its `data` field.
2. With Earth Wireshark capturing TCPCLv3 traffic, run **two sequential Singles** using **NSTART=1**; for each request, confirm the matching Earth `2.01 Created` response and record the **full reassembled TCP length**, rather than the packet-list frame Length.
3. Run **one Aggregate** using **NSTART=2** by queuing the two observations before the 10-second buffer timer expires. Confirm one BPv7 payload containing two decoded CoAP members and two matching Earth responses.
4. Read the BPv7 Payload-Size and TCP reassembled byte count in Earth Wireshark. Calculate savings for the **Rover → Earth request direction**. Return bundles are not included in the byte-saving denominator because both modes produced two Single responses in successful tests.
5. Preserve `.pcapng` files, Rover console logs and JSONL event logs where available. See §9 for evidence and provenance.

The 227-byte line comes from an earlier live Science observation test and was **not yet rerun using the saved fixed 227-byte files**. Do not use it to claim a fully homogeneous five-size controlled dataset.

## 4. Metrics and formulas

Let `p` be the JSON application payload bytes for each POST, `B_S` the BP payload of one Single, `T_S` the reassembled TCP request bytes for one Single, `B_A` the BP payload for one two-member Aggregate, and `T_A` its reassembled TCP request bytes.

```text
CoAP/Single encoding overhead = B_S - p
Two Singles (BP payload)       = 2 × B_S
Two Singles (TCP data)         = 2 × T_S
Aggregation option cost        = B_A - 2 × B_S
Single outer overhead          = T_S - B_S
Aggregate outer overhead       = T_A - B_A
Saved request TCP bytes        = 2 × T_S - T_A
Percent saving                 = 100 × (2 × T_S - T_A) / (2 × T_S)
```

Equivalent overhead decomposition:

```text
Saved bytes = 2 × Single outer overhead
              − Aggregate outer overhead
              − extra Aggregate option bytes
```

**Measurement boundary:** Wireshark's `Reassembled TCP Segments (N bytes)` describes reconstructed TCP stream data carrying serialized BPv7/TCPCL information; it excludes per-packet TCP/IP/Ethernet headers, retransmissions and link-layer traffic. The `Length` cell of the final reassembly packet is **not** the full message size.

## 5. Primary results

| Payload per POST | Single BP payload (each) | Two Singles TCP bytes | Aggregate BP payload | Aggregate TCP bytes | TCP bytes saved | Saving |
|---:|---:|---:|---:|---:|---:|---:|
| 50 B | 97 B | 292 B | 202 B | 251 B | **41 B** | **14.04%** |
| 100 B | 147 B | 392 B | 302 B | 352 B | **40 B** | **10.20%** |
| 227 B | 274 B | 648 B | 556 B | 606 B | **42 B** | **6.48%** |
| 500 B | 547 B | 1,194 B | 1,104 B | 1,154 B | **40 B** | **3.35%** |
| 1,000 B | 1,047 B | 2,194 B | 2,104 B | 2,154 B | **40 B** | **1.82%** |

![TCP data comparison](figures/tcp_data_comparison.png)

![Absolute byte savings](figures/absolute_savings.png)

### Observation and interpretation

The total payload carried as two Singles grows proportionally with message size, whereas the main aggregation saving is avoiding one set of BPv7/TCPCL serialization metadata. Across the five observed points, the request-side saving remains **40–42 B** per pair. Consequently, the **relative saving** decreases with increasing application payload. This comparison does **not** demonstrate a reduced physical packet count, end-to-end delay, or congestion under load.

## 6. Worked calculations

### A. 50-byte Science observations

```text
One Single encoded CoAP/BP payload  = 50 B JSON + 47 B CoAP fields = 97 B
One Single reconstructed TCP data   = 97 B + 49 B outer serialization = 146 B
Two Singles TCP data                = 2 × 146 B = 292 B
Aggregate CoAP/BP payload           = 2 × 97 B + 2 × 4 B Payload-length = 202 B
Aggregate TCP data                  = 202 B + 49 B outer serialization = 251 B
Saved request-side bytes            = 292 B − 251 B = 41 B
Relative saving                     = 41 / 292 × 100 = 14.04%
```

### B. 100-byte Science observations

```text
Two Singles TCP data                = 2 × 196 B = 392 B
Aggregate BP payload                = 2 × 147 B + 8 B = 302 B
Aggregate TCP data                  = 352 B
Saved request-side bytes            = 392 − 352 = 40 B
Relative saving                     = 40 / 392 × 100 = 10.20%
```

### C. 227-byte earlier live Science observations

```text
Two Singles TCP data                = 2 × 324 B = 648 B
Aggregate BP payload                = 2 × 274 B + 8 B = 556 B
Aggregate TCP data                  = 606 B
Saved request-side bytes            = 648 − 606 = 42 B
Relative saving                     = 42 / 648 × 100 = 6.48%
```

### D. 500-byte Science observations

```text
Two Singles TCP data                = 2 × 597 B = 1,194 B
Aggregate BP payload                = 2 × 547 B + 2 × 5 B = 1,104 B
Aggregate TCP data                  = 1,154 B
Saved request-side bytes            = 1,194 − 1,154 = 40 B
Relative saving                     = 40 / 1,194 × 100 = 3.35%
```

### E. 1,000-byte Science observations

```text
Two Singles TCP data                = 2 × 1,097 B = 2,194 B
Aggregate BP payload                = 2 × 1,047 B + 2 × 5 B = 2,104 B
Aggregate TCP data                  = 2,154 B
Saved request-side bytes            = 2,194 − 2,154 = 40 B
Relative saving                     = 40 / 2,194 × 100 = 1.82%
```

### BPv7/TCPCL and Payload-length overhead breakdown

| Payload | Single outer bytes × 2 | Aggregate outer bytes | Extra Payload-length bytes | Net saved |
|---:|---:|---:|---:|---:|
| 50 B | 49 × 2 = 98 | 49 | 8 | **41 B** |
| 100 B | 49 × 2 = 98 | 50 | 8 | **40 B** |
| 227 B | 50 × 2 = 100 | 50 | 8 | **42 B** |
| 500 B | 50 × 2 = 100 | 50 | 10 | **40 B** |
| 1,000 B | 50 × 2 = 100 | 50 | 10 | **40 B** |

The observed Payload-length option costs **4 bytes per member** for values 50, 100, and 227, and **5 bytes per member** for values 500 and 1,000 in this implementation. The difference reflects variable-length encoding of the option value. The outer BPv7/TCPCL serialization overhead also changes slightly with encoded sizes; it must not be assumed to be a universal constant.

## 7. Delivery observations and non-successful attempts

Each **reported successful** Single pair and Aggregate pair produced two matched `2.01 Created` replies. These are individual functional observations, **not enough trials to estimate a delivery probability**.

- **500-byte preliminary Aggregate attempts:** Two isolated POSTs arrived without a second member before `MAX_AGGR_DELAY=10 s`. Each timed out and was sent as a **Single**. They are not included as successful Aggregate request bytes. This shows that an aggregation policy can add ~10 s of queueing delay without saving envelope bytes when the buffer never fills.
- **1,000-byte first Aggregate attempt:** Rover recorded a 2,104-byte Aggregate submission but initially **0/2 responses**. Its cause was not established and should be investigated using its own Earth/Satellite captures and logs. A subsequent separate 1,000-byte Aggregate attempt succeeded with **2/2** responses (Rover MIDs 2543292 / 2543293, Earth response MIDs 81 / 82). This shows 2,104 B aggregation is possible in the tested setup, not that all such attempts are reliable.

**Important:** The reported Rover response interval begins at bundle submission and omits application buffering time. It should not be used as a complete queue-to-response delay without new timestamps. Neither these timing values nor the 2/2 replies establish congestion safety for NSTART=2.

## 8. Valid conclusions and limitations

**Supported conclusions**

1. The prototype can encode and deliver two NON CoAP POST requests to the same destination in one BPv7 Aggregate with corresponding independent responses.
2. For the observed payload sizes, request-side reconstructed TCP data is lower for one Aggregate than for two Singles, by 40–42 bytes per pair.
3. The percentage savings decrease with increasing application payload size in these observed cases (14.04% to 1.82%).

**Not supported yet**

- No claim that aggregation is always beneficial, improves application completion time, or reduces congestion.
- No statistical significance or variability estimate from one successful pair per size; repetitions and confidence intervals are necessary.
- No on-wire Ethernet/IP/TCP byte accounting, CPU/energy measurements, link utilization, loss/backlog tests, or saturated-load results.
- The 227-byte comparison is an earlier non-identical workload and needs an exact fixed-file replication.
- The earlier 1,000-byte unsuccessful trial remains unexplained; it cannot be silently excluded from a future reliability analysis.
- The option-number interoperability caveat noted in §2 remains open.

## 9. Evidence and reproducibility

These tables and figures were reconstructed from the Rover console logs and **screenshots of Earth Wireshark supplied during the experiment**. The report package includes illustrative screenshots but **does not contain raw pcapng capture files**; place original saved captures in the repository for independent verification.

| Payload size | Single request frames (Earth) | Aggregate request frame (Earth) | Captures to retain |
|---:|---|---:|---|
| 50 B | 73, 202 | 16 | Singles and Aggregate `.pcapng` for this size; see notes |
| 100 B | 8, 60 | 11 | Singles and Aggregate `.pcapng` for this size; see notes |
| 227 B | 9, 39 | 36 | Singles and Aggregate `.pcapng` for this size; see notes |
| 500 B | 11, 48 | 13 | Singles and Aggregate `.pcapng` for this size; see notes |
| 1,000 B | 9, 27 | 87 | Singles and Aggregate `.pcapng` for this size; see notes |

**Representative supplied screenshots:**

**50-byte Aggregate:**

![Wireshark 50 B aggregate](evidence/wireshark_50B_aggregate.png)

**500-byte Aggregate:**

![Wireshark 500 B aggregate](evidence/wireshark_500B_aggregate.png)

**1,000-byte successful Aggregate:**

![Wireshark 1000 B aggregate](evidence/wireshark_1000B_aggregate.png)

### Data files

- [`data/measurements.csv`](data/measurements.csv): input observations and derived results for all five payload sizes.
- [`data/verify_calculations.py`](data/verify_calculations.py): checks every formula from the CSV; **does not parse packet captures**.

To recheck the reported math:

```bash
python3 data/verify_calculations.py
```

Recommended destination for raw captures when you transfer them from Earth:

```text
evidence/pcapng/Experiment_C_50B_Two_Singles.pcapng
evidence/pcapng/Experiment_C_50B_Aggregate_NSTART2.pcapng
...matching 100B, 500B, 1000B pairs...
```

These example filenames are storage recommendations, not assertions that the `.pcapng` files were included in this package. The 227-byte run uses earlier captures and should be labeled accordingly.

## 10. Next experiments before congestion-control recommendations

1. **Fixed 227-byte replication:** Re-run both modes with the saved identical JSON files and record new captures.
2. **Replication:** At least several independent matched runs per size, alternating order to reduce time drift; retain failures as well as successes.
3. **Aggregation waiting time:** Measure queue-to-submission and queue-to-response for inter-arrival gaps of approximately 0.1, 1, 5, and >10 s. Avoid relying on response RTT alone.
4. **NSTART=2 safety under continuous connectivity:** Characterize offered load, sustained outstanding interactions, TCPCL queue/backlog/drop counters, completion-time distributions and fairness. Compare with NSTART=1 at matched offered workloads. The present 3-VM isolated lab is not a general safety proof.
5. **Operational policy idea:** Evaluate a *size-, queue-, and deadline-aware aggregation rule* that aggregates only when predicted byte efficiency justifies waiting and the NSTART/congestion limits remain satisfied. This is a **proposed research idea**, not an algorithm prescribed by Draft-05.

## 11. References

1. C. Gomez and A. Calveras, **Constrained Application Protocol (CoAP) over Bundle Protocol (BP)**, Internet-Draft [draft-ietf-core-coap-bp-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp/05/), October 2026, especially §§4.2, 4.3 and 6.
2. IETF, **RFC 9171: Bundle Protocol Version 7 (BPv7)**, https://www.rfc-editor.org/rfc/rfc9171.
3. IETF, **RFC 9758: Updates to the 'ipn' URI Scheme**, https://www.rfc-editor.org/rfc/rfc9758.
4. IETF, **RFC 7252: The Constrained Application Protocol**, §3.1 and §4.7, https://www.rfc-editor.org/rfc/rfc7252.
5. Rover console observations and Earth Wireshark screenshots, collected 7–8 November 2026, supplied by the project team; original raw pcapng and JSONL logs remain on the lab machines unless separately archived.

---

**Suggested citation:** *CoAP over BPv7/IPN experimental notes, Experiment C: Payload Size Versus Aggregation Efficiency (7–8 November 2026).*  
**Scope:** Functional experiment and request-side serialized-byte measurement, not a congestion-control certification.
