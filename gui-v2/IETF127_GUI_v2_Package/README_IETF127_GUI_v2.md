# Mars Rover Mission Control — evidence-aware Draft-05 dashboard

This package is a **safe experimental GUI update** based on the supplied `mission_control.py`.
It does **not** overwrite the existing `Rover_Mission_Control_Draft05_Aggregation.py`,
replace `NodeA`, start/stop/rebuild µD3TN, configure forwarding contacts, or alter the live 3-VM testbed.

## Included files

- `mission_control_v2.py`: redesigned Tkinter GUI (same topology, application cards, five metrics,
  detail-on-click, CSV export, verified/nonverified source labels)
- `rover_live_backend.py`: optional AAP2 + CoAP engine adapter for Rover; it reuses the
  current working NodeA engine, without editing its code or aggregation settings
- `mission_control_v2_preview.png`: screenshot of actual preview mode, with all values N/A

## Three modes — never confused

- `--preview`: show the design with **N/A** in all measurement cards; **no network I/O**.
- `--demo`: explicit simulated visual demonstration; every number is labeled **DEMO**.
- `--live --engine PATH`: connect to the existing Rover CoAP/AAP2 engine; display real
  Rover submission/matched-response events. Other metrics remain **N/A** until
  separate Earth/Satellite/capture evidence is collected.

**The program never automatically falls back to demo mode.**

## Suggested first test on Rover — preview only

1. Save a backup of the existing working GUI and engine; do **not** replace them.
2. Transfer `mission_control_v2.py` and `rover_live_backend.py` to a separate directory
   under `~/CoAPoverBP-IPN-Draft05-NoProxy/applications/rover/dashboard_v2/`.
3. In Rover's terminal:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
"$HOME/coapbp/CoAPoverBP-no-proxy-version/ud3tn/.venv-app/bin/python" \
  applications/rover/dashboard_v2/mission_control_v2.py --preview
```

This displays the GUI while leaving the existing Rover Mission Control and µD3TN unchanged.
If the local Python environment lacks Tkinter, use a Python interpreter with `python3-tk`.

## Later: real Rover AAP2 connection (requires checking your current working engine)

Before starting, **close the old Rover Mission Control GUI** so two independent GUIs do not
register the same AAP2 agent IDs (10 and 11). Leave the existing µD3TN daemon running.
The active forwarding contacts must be current; their one-hour lifetime may have expired.

Identify the currently working NodeA engine file used by
`applications/rover/Rover_Mission_Control_Draft05_Aggregation.py`, and verify it exports
`queue_coap_request`, `coap_receive_loop`, `load_mid_state`, `EVENT_CALLBACK`,
`coap_send_client`, and `coap_receive_client` and reports `queued`, `submitted`,
and `response` events. Verify its MID-state paths before running any live test.

**Only after that compatibility review**, use a command of this form (the ENGINE path must be real):

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
export PYTHONPATH="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/python-ud3tn-utils:$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/pyd3tn${PYTHONPATH:+:$PYTHONPATH}"
"$HOME/coapbp/CoAPoverBP-no-proxy-version/ud3tn/.venv-app/bin/python" \
  applications/rover/dashboard_v2/mission_control_v2.py --live \
  --engine /ABSOLUTE/PATH/TO/YOUR/WORKING/NodeA_Mission_Draft05_IPN.py
```

The live adapter **does not forcibly flush** requests, so it preserves the
engine's NSTART, BUFFER_LIMIT, and MAX_AGGR_DELAY behavior.

## What the five metric cards actually require

| Metric | UI source | Status before instrumentation |
|---|---|---|
| One-way end-to-end delay | Rover bundle submission timestamp + Earth full reception timestamp + measured clock uncertainty | N/A |
| Throughput | bytes at a specified protocol layer received over a **defined measurement window** | N/A |
| Protocol overhead | JSON bytes and associated frame/BPv7/TCPCL bytes from the *same exchange* | N/A |
| Satellite storage wait | two Satellite-side timestamps (monotonic preferred) for receive and forward | N/A |
| Delivery ratio | Earth-logged received requests / Rover-logged submitted requests over settled run | N/A |

The Rover backend may show **application RTT** from a matched response, but it is
not relabeled as one-way delay. Token matching is kept separate from Earth-side
unidirectional delivery counting.

### Optional future metrics feed

`--measurements-jsonl /absolute/path/to/verified_run_records.jsonl`

This is a **future integration interface**, not an existing exporter from the current
Earth or Satellite software. A separate collector must produce matching run records.
Each appended JSONL line can include:

```
app: "science" or "safety"
source: provenance description
rover_submit_utc, earth_recv_utc: absolute synchronized UTC timestamps
clock_checked: true
clock_stepped_during_run: false
clock_uncertainty_ms: numeric independent offset uncertainty (not a claim from `System time` alone)
satellite_receive_monotonic_ns, satellite_forward_monotonic_ns: same Satellite clock
window_seconds: a specified window >= 1 second
window_received_bytes: actual bytes counted on a named hop/layer over that window
json_bytes, associated_captured_frame_bytes, frame_association_verified: true
rover_submitted_count, earth_received_count: matched run totals
layers: dictionary of non-overlapping protocol *overhead contributions* (optional)
```

The GUI calculates:
- One-way delay: `(earth_recv_utc - rover_submit_utc) * 1000`; only with explicit clock-quality proof.
- Measured throughput: `8 * window_received_bytes / (1000 * window_seconds)` kbps.
- Satellite storage wait: `(forward_monotonic_ns - receive_monotonic_ns) / 1e6` ms.
- Measured overhead: `associated_captured_frame_bytes - json_bytes` bytes.
- Earth delivery ratio: `100 * earth_received_count / rover_submitted_count`.

A collector must also link each record to the same *run / bundle / token* and distinguish
the Rover→Satellite and Satellite→Earth hops; the sample schema alone cannot guarantee
scientific validity. Do not add the historical 350-byte baseline as if it were a live value.

## Important corrections already applied

- Both link labels now say **TCPCLv3** (not TCPCLv4).
- Exact application resource paths are `/mission/safety-guidance` and `/science/observations`.
- CoAP URI authority uses `64.3.0.ipn.alt`.
- Live mode has **no link-cut button or key**, and **auto-run is disabled**.
- No animation of simulated travel times in LIVE mode.
- Unknown metric values show **N/A** rather than fake zero/green.
- Click a measurement tile to inspect its definition, data source, timestamps, and evidence.
- Real results and demo simulations are tagged separately in GUI and CSV export.
- TCP/data rate is labeled **kbps** (bits/s), not KB/s (bytes/s).

## What is still not implemented

The current attached files do not include the running Earth/Satellite instrumentation
or the exact current `Rover_Mission_Control_Draft05_Aggregation.py` implementation.
Thus, this package does **not** yet collect all five metrics live, and its
Rover adapter must be checked against the active NodeA engine before experiments.

**Do not use `--demo` values as research data.** Preserve packet captures and
run logs for verification before presenting results to Prof. Anna or IETF 127.
