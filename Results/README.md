# Results — IETF 127 CoAP/BPv7 Hackathon

This folder is **for experimental research results and charts**, NOT for synthetic GUI measurements. It is safe to commit `scripts/`, `templates/`, `protocols/`, and curated charts. Avoid committing sensitive/incomplete raw traces without reviewing them first.

## Workflow

1. Run `gui-v2/IETF127_GUI_v2_Package/run_gui_live_results.sh` on Rover, plus the three existing `live_capture_agent.py` processes on the appropriate VMs.
2. Each GUI launch creates a new UTC run ID. Live telemetry is appended to `Results/raw/<RUN_ID>.jsonl`, and bundle/CoAP event records to `Results/raw/<RUN_ID>_events.jsonl`.
3. Charts regenerate automatically when you close the GUI. To create them manually during a run, execute from repository root:

   `python3 Results/scripts/generate_results.py --root Results --nstart 1`

   For a documented, approved controlled NSTART=2 run, use `--nstart 2` instead. Alternatively start `python3 Results/scripts/watch_results.py --nstart 1` in another Rover terminal to update the charts every 10 seconds. Ctrl+C stops only the chart watcher.
4. Open `Results/charts/*.svg` directly in a browser or insert the included PNG/SVG versions in PowerPoint. Fresh experiment charts are regenerated as SVG (stdlib-only; PNG conversion is optional). `Results/tables/*.csv` are reusable for publication. The `SUMMARY.md` records exactly how many observations each chart uses.
5. Commit curated run charts and descriptions with a reproducibility note, including run ID, software commit, port topology and test parameters. Keep original evidence and per-node clock logs available for validation.

## Charts

- `application_rtt.svg`: Rover-observed RTT from real matched responses.
- `single_vs_aggregate.svg`: **actual engine submission type**; never infer from two button presses.
- `earth_receipt_progress.svg`: correlated Earth receipt progress; not final packet loss until settled.
- `satellite_earth_link_rate.svg`: TCPCL link payload rate over a fixed window, **not CoAP goodput**.
- `data_bearing_overhead.svg`: limited, verifiable Ethernet minus BPv7 payload association; not full overhead.
- `outstanding_nstart.svg`: observed outstanding interactions vs the *configured report cap*.

Missing validated delay and Satellite storage wait remain N/A. Numerical values are not synthesized.

## Preliminary observations

`preliminary/` contains **only 2 screenshot-derived Rover RTT observations and 1 decoded bundle pair**, not a statistical experiment. These are labeled separately from new run results. For your paper, replace them with replicated measurements from a settled, reproducible run.
