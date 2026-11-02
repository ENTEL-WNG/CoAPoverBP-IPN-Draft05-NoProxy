# Protocol architecture and laboratory topology

| Role | Internal VM IP | µD3TN node EID | TCPCLv3 port | AAP2 Unix socket | Application service |
| --- | --- | --- | ---: | --- | --- |
| Rover | `192.168.100.3` | `ipn:0.1.0` | 4671 | `/tmp/ud3tn-ipn3-lab.aap2.sock` | Safety `ipn:0.1.10`; Science `ipn:0.1.11` |
| Satellite | `192.168.100.2` | `ipn:0.2.0` | 4672 | `/tmp/ud3tn-ipn3-sat.aap2.sock` | BPv7 relay; **no CoAP proxy** |
| Earth | `192.168.100.1` | `ipn:0.3.0` | 4673 | `/tmp/ud3tn-ipn3-earth.aap2.sock` | CoAP server `ipn:0.3.64` |

- Direct CoAP-over-BP sending and receiving take place via modified µD3TN/AAP2 and aiocoap. The bundle destination is the Earth **application endpoint** `ipn:0.3.64` while the Earth **node** EID is `ipn:0.3.0`.
- URI authority `64.3.0.ipn.alt` is mapped within the application to `ipn:0.3.64`; `.ipn.alt` is not resolved using DNS.
- Rover Safety invokes `GET /mission/safety-guidance`; Science sends `POST /science/observations`.
- Two distinct Rover AAP2 application registrations and independent pending request/MID/buffer state. Their NSTART=2 settings do **not** constitute cross-application congestion control.
- Contact configuration is directional: Rover→Satellite→Earth; Earth→Satellite→Rover. Scripts request **one-hour** contacts, which must be renewed if they expire. There is no separately demonstrated asynchronous outage scenario in the November 1 success evidence.
- Modified CoAP wire format has a **24-bit MID** and experimental **Payload-length option 65000**. For aggregation each member includes Payload-length and the two encoded messages are concatenated into a single BPv7 application payload.
- Earth disaggregates and processes each CoAP request; the tested path sends **individual Single responses** and correlates by Token.

For saved packet-level and response-correlation evidence see [results](results.md), [IETF demo](ietf-demo.md), and the `.pcapng` files in `evidence/`. Verified BPv7 application payload sizes: **116 B** for two Safety GETs, **556 B** for two Science POSTs.
