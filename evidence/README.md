# Wireshark Evidence — CoAP over BPv7 with Three-Component IPN Addressing

## Overview

This folder contains Wireshark packet captures (`.pcapng`) and supporting screenshots demonstrating the implementation of **CoAP over Bundle Protocol Version 7 (BPv7)**, based on `draft-ietf-core-coap-bp-05`, using **RFC 9758 three-component IPN endpoint identifiers**.

The experiments were conducted using a three-node Delay-Tolerant Networking (DTN) testbed consisting of a Mars Rover, Satellite relay, and Earth station.

The implementation uses µD3TN, AAP2, TCPCLv3, and a modified CoAP implementation, with direct CoAP-over-BPv7 communication and no CoAP proxy.

## Network Configuration

| Node | IP Address | IPN Endpoint Identifier | TCPCLv3 Port |
|---|---|---|---|
| Rover | 192.168.100.3 | `ipn:974848.1.0` | 4771 |
| Satellite | 192.168.100.2 | `ipn:974848.2.0` | 4772 |
| Earth | 192.168.100.1 | `ipn:974848.3.0` | 4773 |

**Application endpoints:**
- Rover Safety: `ipn:974848.1.10`
- Rover Science: `ipn:974848.1.11`
- Earth CoAP Server: `ipn:974848.3.64`

All current endpoint identifiers use allocator **974848**, rather than the earlier allocator 0.

## Wireshark Capture Contents

The main Wireshark capture contains both **Single and Aggregate CoAP-over-BPv7 exchanges**, allowing comparison of the two transmission modes.

### 1. Single CoAP Messages

The capture demonstrates:

- NON CoAP GET requests sent from Rover to Earth.
- Each request encapsulated in an individual BPv7 bundle.
- Successful Earth responses (`2.05 Content`).
- Verification of source and destination IPN identifiers.
- Inspection of BPv7 primary blocks and application payloads.

### 2. Aggregate CoAP Messages

The capture demonstrates:

- Two NON CoAP POST requests combined into one BPv7 bundle.
- A single Aggregate application payload of **212 bytes**.
- Distinct CoAP Message IDs and Tokens for the two requests.
- Payload-length information for each aggregated message.
- Successful processing by the Earth CoAP application.
- Two corresponding `2.01 Created` responses transmitted as separate Single bundles.

**Important Wireshark evidence:** Frame 76 demonstrates the two-member Science Aggregate, including its 90,000 ms BPv7 bundle lifetime.

### 3. RFC 9758 Three-Component IPN Verification

Wireshark 4.6.9 verifies:

- IPN Scheme Code: 2
- IPN Element Count: 3
- IPN Allocator: 974848
- Source: `ipn:974848.1.11`
- Destination: `ipn:974848.3.64`

This confirms the three-component IPN representation used by the updated implementation.

## Opening and Analyzing the Captures

Open the `.pcapng` files using **Wireshark 4.6.9**.

The repository includes an experimental Lua dissector:

`wireshark/coapbp05_ipn64_PL65000.lua`

This dissector provides additional visibility into CoAP-over-BPv7 Single and Aggregate messages, including Message IDs, Tokens, CoAP options, and Aggregate member counts.

Useful Wireshark display filters:

```text
bpv7
```

```text
tcp.port == 4773
```

```text
bpv7.eid.ipn_count == 3
```

```text
bpv7.eid.ipn_alloc == 974848
```

```text
coapbp05.count == 2
```

The final filter requires the experimental Lua dissector.

## Evidence and Reproducibility

The packet captures are provided to allow Hackathon participants and researchers to inspect the actual BPv7 traffic and verify the CoAP messages carried inside the bundles.

The captures demonstrate successful functional exchanges in the tested configuration. They do not, by themselves, establish general network reliability, congestion-control safety, or complete interoperability with Draft-05.

Historical captures using allocator 0 should be identified separately and must not be presented as allocator-974848 results.

## References

- [CoAP over BPv7 — Internet-Draft](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/)
- [RFC 9171 — Bundle Protocol Version 7](https://www.rfc-editor.org/rfc/rfc9171)
- [RFC 9758 — IPN URI Scheme Update](https://www.rfc-editor.org/rfc/rfc9758)

## Project Information

**Project:** CoAP over BPv7 with IPN Addressing and Message Aggregation

**Event:** IETF 127 Hackathon — November 2026

**Affiliation:** Universitat Politècnica de Catalunya (UPC), Wireless Networks Group (WNG)

**Champions:**
- Prof. Anna Calveras — Onsite Champion
- Mahitab Salah Elattar — Remote Champion

**AI Assistance:** AI tools were used to assist with documentation preparation, editing, and development support. Experimental evidence originates from Wireshark captures and implementation tests.
