# IETF 127 Aggregate Bundle Demo

An English-subtitled, silent walkthrough of CoAP over BPv7 application-layer aggregation in the Rover–Satellite–Earth testbed.

The demonstration uses **Aggregate mode (NSTART=2)** and two Rover Science NON POST messages, combined at the application endpoint into **one BPv7 request bundle**. In the verified run, Wireshark decoded two members, each with Payload-length option 65000 set to 227 bytes, and two matching Earth `2.01 Created` responses. The request BP payload was 556 bytes, with a verified 90,000 ms bundle lifetime.

- Video: `IETF127_Aggregate_Demo.mp4`
- English subtitles: `IETF127_Aggregate_Demo.srt`

The video is edited from actual testbed screenshots and is not an uninterrupted live screen recording. It does not constitute a separate congestion-safety validation for NSTART=2.
