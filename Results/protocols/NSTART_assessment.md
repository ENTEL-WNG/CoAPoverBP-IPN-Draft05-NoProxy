# NSTART congestion-control assessment (required before controlled Aggregate test)

**Governing rule:** RFC 7252 §4.7 limits outstanding interactions from each CoAP client to a server to NSTART, default **1**. Draft-05 §6 applies the same cap to the count of outstanding Singles in one Aggregate. NON messages are not exempt.

This GUI starts with **NSTART ceiling 1** regardless of the NodeA engine's existing `NSTART=2`; it does not change the engine. Two queued requests of the **same client application** may be combined only in an explicitly approved test with a **GUI ceiling of 2** and an engine NSTART >= 2. Safety and Science have different EIDs; they must NOT be combined into one Aggregate. The shared-link GUI cap is also 2 to avoid oversubscribing the bottleneck from both clients simultaneously.

## Before enabling NSTART=2, record actual deployment characteristics

1. Measure bottleneck capacity in bit/s (both directions), ON duration, OFF duration, RTT distribution (especially P95/P99), queue occupancy and burst size under the current contact schedule.
2. Obtain a conservative **full on-wire** bundle-size upper bound (payload plus BPv7/TCPCL/TCP/IP overhead), with concurrent backlog. `check_contact_budget.py` evaluates a **necessary but not sufficient** capacity bound: `NSTART × bundle_upper_bytes + queued_bytes <= link_bps × contact_seconds / 8 × safety_fraction`.
3. Measure delivery/timeout/retransmission and queue growth against the NSTART=1 baseline. If queue growth, loss, repeated timeouts, missed contact windows, or unstable RTT occur, retain NSTART=1 or reduce load; do not automatically raise NSTART.
4. Configure explicit contact-aware pacing, MAX_AGGR_DELAY, bundle lifetime, queue limits, and a bounded aggregate of **at most two Singles** from the **same** source EID and destination EID; stop on congestion symptoms.
5. Preserve logs with `run_id`, link settings, NSTART, observed max outstanding, transmission type and Earth receipts. The CLI guard is an additional GUI-only limit; it does **not** regulate other AAP2 clients or make NSTART=2 inherently safe.

## Controlled experiment opt-in (only after assessment)

`IETF127_CC_NSTART2_APPROVED=YES bash run_gui_live_results.sh`

Your existing NodeA uses `BUFFER_LIMIT=2` and `NSTART=2` (from previous terminal output). This opt-in does not modify those values and is **not a claim of full congestion safety**. Test NSTART=1 baseline first; the GUI guard then blocks a second outstanding interaction. A higher NSTART requires stronger deployment-specific congestion controls than this ceiling alone.

## Evaluation cases

- Baseline: NSTART=1, 1 NON GET; expect **SINGLE**.
- Controlled: NSTART=2 (only after assessment), 2 NON GET requests from `ipn:0.1.10` to `ipn:0.3.64` queued within the engine aggregation window; expect **AGGREGATE (2 CoAP Singles)** *only if the engine actually submits such a bundle*.
- Congestion stress: repeat with measured higher RTT/outage, compare P95 RTT, receipts, queued bytes, and whether guard blocked requests. No automatic NSTART increase.

Sources: https://www.rfc-editor.org/rfc/rfc7252.html#section-4.7 and https://datatracker.ietf.org/doc/html/draft-ietf-core-coap-bp-05#section-6
