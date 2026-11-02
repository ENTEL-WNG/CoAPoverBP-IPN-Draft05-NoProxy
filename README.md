# CoAP over BPv7 — IPN Draft-05, no proxy

Experimental CoAP-over-BPv7 implementation with three-component IPN endpoint identifiers, µD3TN/AAP2, two isolated CoAP application endpoints on Rover, Single/Aggregate requests, and Wireshark packet analysis.

**Status:** Research prototype; **not claimed to be fully interoperable or Draft-05 conformant**. The currently deployed prototype uses experimental Payload-length option **65000** and experimental **NSTART=2 per Rover application**. The Draft-05 option assignment and safe congestion-control settings require further review.

## Architecture

```text
Rover 192.168.100.3                Satellite 192.168.100.2         Earth 192.168.100.1
µD3TN ipn:0.1.0 :4671             µD3TN ipn:0.2.0 :4672        µD3TN ipn:0.3.0 :4673
Safety GET ipn:0.1.10    ----->    BP relay                 ---->   CoAP server ipn:0.3.64
Science POST ipn:0.1.11  ----->    (store / forward)       ---->   /mission/safety-guidance
                                                                     /science/observations
```

CoAP URI authority: `64.3.0.ipn.alt`, corresponding to Earth CoAP endpoint `ipn:0.3.64`. Both rover services implement CoAP and use separate AAP2 registrations and per-application experiment state.

## Demonstrated behavior (2026-11-01)

- Rover sends one **116-byte BPv7 payload** containing **two CoAP NON Safety GET** requests. Earth decodes two different MIDs/Tokens and sends two separate NON responses, each correlated by Token.
- Rover sends one **556-byte BPv7 payload** containing **two CoAP NON Science POST** requests (Payload-length **227** in each CoAP message). Earth decodes both and sends two separate **2.01 Created** responses.
- Earth Wireshark capture: Science request **frame 14**, 556-byte BPv7 payload, CoAP MIDs **4858056** and **4858057**, Tokens **9fc152cf** and **5ae01fab**; responses **frames 31 and 49**, each BPv7 payload **54 bytes**, matching Tokens. This capture confirms two members and two correlated responses **at Earth's capture point**; end-to-end rover delivery should also be verified with Rover logs for the same run.
- Wireshark Lua dissector expands the CoAP members under BPv7, including 24-bit MID, Token, URI and experimental Payload-length option 65000.

See [docs/results.md](docs/results.md) and [docs/reproduction.md](docs/reproduction.md).

## Directory guide

- `applications/rover/` — working Draft-05 CoAP aggregation client and Rover Mission Control GUI.
- `applications/earth/` — current live `NodeB_Mission_Draft05_IPN.py` (copy from Earth VM).
- `patches/ud3tn/` — verified nine-file patch for three-component IPN addressing and AAP2 support.
- `vendor/aiocoap/` — collected modified aiocoap source, packaging metadata, and license files.
- `wireshark/` — Lua dissector, source configuration and usage notes.
- `scripts/` — known working contact-route and app startup examples; µD3TN launch scripts still need to be documented.
- `experiments/` and `evidence/` — experiment metadata, terminal logs and **actual .pcapng captures** copied from Earth, not synthetic captures.
- `docs/` — topology, experiment findings, reproducibility and upstream provenance.

## Prepare and publish

The working Rover and Earth applications, modified aiocoap source, verified µD3TN patch, Wireshark decoder, and Safety/Science Aggregate captures have been collected. Fresh-clone installation and end-to-end reproduction are not yet validated. See [source collection](docs/source-collection.md) for provenance notes. Do not commit credentials, runtime state, virtual machines, or backups.

The new GitHub repository was created at `https://github.com/ENTEL-WNG/CoAPoverBP-IPN-Draft05-NoProxy`. Confirm you have organization push permission before uploading.
