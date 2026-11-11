IETF 127 — LIVE TCPCL/BPv7 Measurement Dashboard
================================================

PURPOSE
-------
Keep the compact Mission Control dashboard layout and the existing working
Rover NodeA / Earth NodeB / three µD3TN processes unchanged. Observe the
current traffic on each VM with TShark, feed statistics to the Rover GUI, and
update measurement tiles while requests are sent.

The capture agents DO NOT start or stop µD3TN; DO NOT modify iptables,
forwarding rules, TCPCL sockets, AAP2 registrations, or CoAP implementation.
The agents send observation metadata over a separate UDP channel to Rover
(192.168.100.3:56786); this is NOT a DTN bundle and is excluded from captures.

CONTENTS
--------
mission_control_v2_live_metrics.py — compact GUI plus live capture listener;
   import of existing rover_live_backend.py stays unchanged
live_metrics_hub.py — correlates Rover AAP2 submit events and TShark BPv7
   bundle identities from Rover, Satellite, and Earth; writes JSONL
live_capture_agent.py — stdlib-only, read-only live TShark agent on any VM
selftest_live_metrics.py — offline parser/correlation unit tests
run_gui_live.sh — optional Rover GUI launcher matching your working Python env

TO START — CLOSE YOUR OLD COMPACT GUI FIRST
------------------------------------------
Place IETF127_Live_Capture_Measurements.zip inside Rover ~/Downloads.

ROVER (terminal 1):
  cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_GUI_v2_Package
  unzip -o ~/Downloads/IETF127_Live_Capture_Measurements.zip -d .
  python3 selftest_live_metrics.py
  bash run_gui_live.sh

The GUI should open in LIVE mode and say the live-capture listener is active.
Do not send GET yet. Do not run the old compact GUI simultaneously.

ROVER (new terminal 2), while the live GUI stays open:
  cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_GUI_v2_Package
  sudo /usr/bin/python3 live_capture_agent.py --node rover --collector 192.168.100.3

SATELLITE (separate Satellite VM terminal):
  mkdir -p ~/ietf127_live_capture
  unzip -o ~/Downloads/IETF127_Live_Capture_Measurements.zip live_capture_agent.py -d ~/ietf127_live_capture
  sudo /usr/bin/python3 ~/ietf127_live_capture/live_capture_agent.py --node satellite --collector 192.168.100.3

EARTH (separate Earth VM terminal):
  mkdir -p ~/ietf127_live_capture
  unzip -o ~/Downloads/IETF127_Live_Capture_Measurements.zip live_capture_agent.py -d ~/ietf127_live_capture
  sudo /usr/bin/python3 ~/ietf127_live_capture/live_capture_agent.py --node earth --collector 192.168.100.3

NOTE: the zip must be copied/downloaded to EACH VM's Downloads folder before
running the Satellite/Earth commands. Only the capture agent is needed there.
If `tshark` does not capture on a VM, run
  sudo /usr/bin/python3 live_capture_agent.py --node earth --check-only
(change node as applicable) and inspect the output.

NOW RUN THE LIVE TEST
---------------------
1. In Rover GUI event log verify 'ROVER', 'SATELLITE', 'EARTH LIVE capture agent connected'.
2. Press Safety GET ONCE; observe the new events as real requests traverse the VMs.
3. Repeat with Science POST when Safety works.
4. Keep all three agent terminals running during tests. Press Ctrl+C only in
   the AGENT terminal to stop observation. Close GUI with its X.
5. JSONL evidence is appended to ~/ietf127_evidence/live_metrics.jsonl on Rover.

WHAT WILL DISPLAY (AND WHAT WILL NOT)
-------------------------------------
- Application RTT: real matched CoAP response interval from existing Rover
  backend. This is not one-way end-to-end delay.
- Throughput: rolling 5-second goodput on Satellite->Earth link, defined as
  TCP payload bytes captured at Earth over the 5-second window. It reaches 0
  when no data is arriving; this is EXPECTED, not a crash.
- Delivery ratio: confirmed same BPv7 bundle ID at Rover and Earth, paired
  with Rover backend AAP2 submission batches; counts members of an Aggregate
  only when they were submitted together by NodeA. This confirms BPv7 arrival
  at Earth, not independently CoAP server acceptance.
- Protocol overhead: only if a SINGLE packetized bundle can be unambiguously
  associated with a complete TCPCL transfer at Earth. Computation uses the
  Ethernet data-bearing frames minus BPv7 payload bytes. Excludes reverse ACK
  frames. Remains N/A rather than guessing when the capture is ambiguous.
- Satellite storage wait: only if a distinct TCPCL outgoing START marker can
  be associated with the complete incoming bundle. Otherwise N/A.
- One-way end-to-end delay: intentionally N/A in this first version. Current
  chrony status alone does not prove no clock step occurred during the run;
  adding a separately verified clock monitor is required for this metric.

The measurement metadata is out-of-band over UDP to preserve the traffic
path. Actual CoAP request/response exchanges remain BPv7 via Rover-Satellite-Earth.

TROUBLESHOOTING
---------------
- If GUI reports an import error, use run_gui_live.sh from the same Rover
  directory that already runs your working compact GUI; ensure
  .gui-live-deps/aioconsole exists.
- If a capture agent prints an error about unsupported TShark fields, send
  its output along with `tshark --version`. Versions of the dissector differ.
- If an agent says listening but no frames arrive: check that the VM has
  enp0s8 at 192.168.100.1/.2/.3 and that TShark can capture with sudo.
- If the GUI does not report 'EARTH LIVE capture agent connected', test UDP
  connectivity between 192.168.100.1 and 192.168.100.3 (port 56786). Do not
  alter the firewall before inspecting current rules.
- If a valid Earth GET reply is observed in CoAP but no delivery ratio:
  make sure all three TShark agents were running BEFORE clicking GET. An
  isolated Rover packet is not enough to tie a submission to a bundle ID.

SAFETY
------
This is a live prototype: tested with offline packet-event fixtures and a
Tkinter preview smoke test. It has NOT been run against your three VM network
from ChatGPT. Confirm event log and numbers on your VMs before presenting.
