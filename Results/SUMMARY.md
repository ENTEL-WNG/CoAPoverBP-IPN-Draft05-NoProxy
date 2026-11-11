# IETF 127 Results — 20261108T223655Z

- Events file: /home/mahi/CoAPoverBP-IPN-Draft05-NoProxy/Results/raw/20261108T223655Z_events.jsonl
- Matched application RTTs: 0
- Bundles submitted: 1; SINGLE=1, AGGREGATE=0
- Verified Earth receipt events: 0
- Max outstanding tokens by application: {'safety': 1}; NSTART report limit: 1
- Outstanding cap violations in observed event trace: none detected (trace only)
- Link-rate records: 0
- Verified overhead records: 0

## Interpretation safeguards

- A successful CoAP response is not by itself an Earth receipt count; only BPv7-correlated receipts are used.
- The percentage received/submitted is provisional until a settled run has elapsed.
- Missing one-way delay/storage wait remains unmeasured; do not replace N/A with zero.
- Packet-level link rate is NOT CoAP application goodput.
- Frame-overhead plot excludes reverse TCP ACKs and is NOT an estimate of every protocol layer.
- NSTART=2 requires separately documented congestion-control justification and safety mechanism; a guard alone is not proof of safety.
