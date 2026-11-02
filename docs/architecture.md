# Architecture and testbed

| Node | Internal interface | µD3TN EID | TCPCLv3 | AAP2 socket |
| --- | --- | --- | ---: | --- |
| Rover | enp0s8 `192.168.100.3` | `ipn:0.1.0` | 4671 | `/tmp/ud3tn-ipn3-lab.aap2.sock` |
| Satellite | enp0s8 `192.168.100.2` | `ipn:0.2.0` | 4672 | `/tmp/ud3tn-ipn3-sat.aap2.sock` |
| Earth | enp0s8 `192.168.100.1` | `ipn:0.3.0` | 4673 | `/tmp/ud3tn-ipn3-earth.aap2.sock` |

CoAP applications: Rover Safety GET source `ipn:0.1.10`, Science POST source `ipn:0.1.11`; Earth destination `ipn:0.3.64`. The rover uses `coap://64.3.0.ipn.alt/...` authority. The Satellite functions as a BP relay (not a CoAP proxy).

**Contacts:** Rover→Satellite, Satellite→Earth, Satellite→Rover, Earth→Satellite; four directional routing/contact commands in `scripts/`. The example contact schedules last 3600 seconds and must be refreshed for later tests. Ensure all three µD3TN daemons and Earth's server are up before triggering requests.

**Current experiment**: buffer limit 2, aggregation timer 10 s, experimental NSTART 2 per application. The two application clients have independent state. Cross-application congestion-control policy and more realistic scheduled outage tests remain open work.

**Protocol implementation**: modified µD3TN (C EID/CBOR path) and AAP2 Python utility, modified aiocoap (24-bit CoAP MID and Payload-length option 65000). The deployed source must be copied or patched into the repo, with upstream commit IDs recorded.
