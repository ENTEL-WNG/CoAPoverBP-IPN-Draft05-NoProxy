# Recording future experiments

The included `evidence/` directory contains actual Earth `.pcapng` captures of the successful November 1, 2026 Safety and Science Aggregate tests. Their verified properties are described in [docs/results.md](../docs/results.md) and [docs/ietf-demo.md](../docs/ietf-demo.md). Do **not** fabricate additional runs or mix MIDs/Tokens from distinct captures.

For each subsequent run create a folder, for example `experiments/2026-11-xx-safety-aggregate/`, containing a short Markdown summary with: date/time (time zone), Git commit and patched µD3TN revision, installed Python versions, VM EIDs and IPs, contacts including ON/OFF, NSTART/aggregation buffer/delay, payload description, exact request-response Tokens/MIDs, delivery and delay metrics, and a link to the corresponding Earth `.pcapng`. Optionally add **sanitized** Rover and Earth log excerpts, matched to the same run. Do not commit credentials, private data, VM images or unredacted large debug logs.

This directory contains experiments evaluating CoAP over BPv7 performance, including aggregation efficiency, waiting time, and congestion control.
