# Verified experiment results

## Safety (CoAP NON GET)

- Request source/destination: `ipn:0.1.10` → `ipn:0.3.64`.
- Two Safety GET messages encoded into **one BPv7 payload (116 bytes)**.
- Two independently parsed MIDs and Tokens; each CoAP request carries Payload-length **3**.
- Earth replied with two Single NON **2.05 Content** responses; Rover logs from that run showed both response Token matches and pending requests returned to 0.
- Example pair from Rover/Earth logs: MID `12410189`, Token `d7ef6f92`; MID `12410190`, Token `3fda244f`.

## Science (CoAP NON POST)

- Request source/destination: `ipn:0.1.11` → `ipn:0.3.64`.
- Two Science POST messages encoded into **one BPv7 payload (556 bytes)**.
- Payload-length **227 bytes per CoAP member**; separately matched 2.01 Created responses.
- Example *earlier console test*: MIDs `4858053` and `4858054`, both responses matched on Rover.
- Example *Wireshark-captured run*: frame **14**, request MIDs `4858056` and `4858057`, Tokens `9fc152cf` and `5ae01fab`. Response frames **31** and **49** (54-byte BPv7 payload each) contain corresponding Tokens and CoAP code 2.01 Created.
- The captured run and earlier console test are **different runs**; do not combine their MIDs or assume the current Wireshark run proved Rover reception without corresponding Rover logs.

## Caveats and follow-up

- AAP2 application submissions and Wireshark packet decoding are confirmed; this does not establish full Draft-05 conformance.
- Response aggregation is not implemented in this tested path; Earth sends two individual Single response bundles.
- Experimental Payload-length CoAP option **65000** is not a finalized standard option assignment; its bit semantics require reviewing against the current draft.
- NSTART **2** is a controlled local setting, not a congestion-safety proof. Current implementation maintains separate per-application counts.
- Experiment comparisons should measure wire bytes (TCPCL/BPv7 overhead included), latency, useful-data efficiency, and loss under planned disruptions.
