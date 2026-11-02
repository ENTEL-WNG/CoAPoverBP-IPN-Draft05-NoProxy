# Upstream provenance and licensing

Before publishing, record:

| Component | Upstream URL | Base commit/tag | Local changes | License |
| --- | --- | --- | --- | --- |
| µD3TN | TODO | TODO | EID parser/encoder, CBOR, AAP2, routing integration | TODO |
| aiocoap | TODO | TODO | 24-bit MID, Payload-length (65000), Aggregate serialization/decoding | TODO |
| Local Rover/Earth app code | Source from deployed VMs | n/a | Mission GUI, IPN endpoints, server and tests | Review authorship |
| Wireshark Lua dissector | Project experimental script | n/a | Service 10/11/64 CoAP-over-BPv7 | Project |

Choose a repository LICENSE with the research group; do not remove upstream SPDX headers or bundle third-party code without preserving attribution and its license conditions.

## Verified Draft-05 IPN implementation

Laboratory source Git commit:
37b968d5742cbd75292b534f3421fac70acc46b7

µD3TN:
- Nine-file source patch in patches/ud3tn/
- Patch validated against the original Git index
- Patch reverse-validated against the modified source

aiocoap:
- Modified source included in vendor/aiocoap/
- Active message.py verified against exported source using SHA-256
- Experimental Payload-length option: 65000

Experimental status:
- Three-component IPN addressing
- CoAP Single and Aggregate request handling
- Safety GET and Science POST
- Experimental NSTART=2
- Wireshark decoding and verified Aggregate captures

Limitations:
- Fresh-clone installation has not been validated
- Startup scripts retain laboratory-specific paths
- Congestion-control safety and full Draft-05 conformance
  have not been established
