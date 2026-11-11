# IETF 127 Hackathon Media

## CoAP over BPv7 with IPN Addressing and Message Aggregation

This directory contains demonstration videos, subtitle files, and supporting documentation prepared for the IETF 127 Hackathon project **CoAP over BPv7 with IPN Addressing and Message Aggregation**.

The project investigates the operation of the Constrained Application Protocol (CoAP) over Bundle Protocol Version 7 (BPv7), following `draft-ietf-core-coap-bp-05`.

The implementation focuses on:

- Three-component IPN Endpoint Identifiers (EIDs), following RFC 9758.
- Direct CoAP-over-BPv7 communication without application-layer proxies.
- Non-confirmable (NON) CoAP messages.
- Message aggregation and bundle-level inspection.
- Wireshark-based protocol analysis and experimental validation.

## Directory Contents

This directory is organized into three demonstration folders.

### 1. IETF127_Single_Bundle_Demo

Contains demonstration material for transmitting individual CoAP messages over BPv7.

The demonstration covers the Rover–Satellite–Earth testbed, CoAP message encapsulation, three-component IPN addressing, and forwarding over the delay-tolerant network.

The accompanying material supports examination of individual BPv7 bundles and end-to-end communication using Wireshark.

### 2. IETF127_Aggregate_Bundle_Demo

Contains demonstration material illustrating the CoAP message aggregation mechanism considered in the project.

The material explains the purpose of combining multiple CoAP messages into a BPv7 bundle, the distinction between single-message and aggregate transmission, and the relevant message-identification and validation considerations.

Where applicable, protocol captures and demonstration evidence should be used to distinguish implemented and verified behavior from illustrative explanations.

### 3. IETF127_Lua_Dissector_Tutorial

Contains an instructional demonstration of Wireshark 4.6.9 and the Lua-based protocol analysis workflow used in the project.

The tutorial covers:

- Configuring the Lua dissector.
- Capturing traffic from the experimental testbed.
- Inspecting TCPCLv3 and BPv7 packet structures.
- Examining three-component IPN source and destination EIDs.
- Interpreting the encapsulated CoAP messages and relevant protocol fields.
- Using packet captures as reproducible experimental evidence.

## Demonstration Files

Each folder may contain an MP4 demonstration recording, an associated SRT subtitle file, and supplementary explanatory documentation.

These resources are intended to help Hackathon participants understand the experimental architecture, follow the demonstration procedures, and examine protocol behavior.

## Technical References

- [CoAP over BPv7 — Internet-Draft](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/)
- [RFC 9171 — Bundle Protocol Version 7](https://datatracker.ietf.org/doc/rfc9171/)
- [RFC 9758 — Three-Component IPN EIDs](https://datatracker.ietf.org/doc/rfc9758/)

## AI-Assisted Editing Disclosure

AI-assisted tools were used to support the editing and presentation of the demonstration videos, including improvements to visual organization, text, subtitles, and overall presentation quality.

AI assistance was used for media editing and documentation preparation. The technical implementation, experimental validation, and interpretation of results remain the responsibility of the project team.
