# Demo video

Place final Hackathon screen recording here, e.g. `IETF127_CoAPoverBP_Live_Demo.mp4` (not included because no video has been recorded yet). Before publishing a video, verify that no tokens, credentials or personal material are visible.

Suggested **5–8 minute** recording storyboard:

1. Title + three-VM IPN layout (Rover `ipn:0.1.10` / Satellite `ipn:0.2.0` / Earth `ipn:0.3.64`).
2. Screenshot of GUI with both Safety and Science AAP2 registrations (no measurement tiles).
3. Press Safety GET once; event log should explicitly display **SINGLE**, matched 2.05 Content and application RTT.
4. After documented contact and congestion safety checks, enable NSTART=2 and submit **two requests from Safety** in the aggregation window. Point to **AGGREGATE (2 CoAP Singles)** in the event log; if it remains Single, say so and investigate rather than narrate an unobserved result.
5. Show Wireshark / TShark BPv7 request identity with source/destination and matching forward frames, and the response path.
6. Open real SVG charts from Results; explain safety guard, cap, and which metrics are still unverified.
7. End with conclusions, current limitations, draft-05 scope (IPN, NON, no proxy).

Video should be recorded on the VM/desktop using an available screen recorder. This repository folder contains no fabricated demonstration recording.
