IETF 127 Mars Rover Mission Control — Compact version

Purpose:
  Keep the original side-by-side GUI layout and shrink spacing, fonts,
  topology canvas, and measurement panels to fit a VirtualBox screen.
  No scrolling. Does not change live backend or network behavior.

Install on Rover VM:
  cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_GUI_v2_Package
  unzip ~/Downloads/IETF127_Mission_Control_Compact_Fit.zip -d .

Preview:
  python3 mission_control_v2_compact.py --preview

Live (after closing previous GUI and restoring the working Python 3.10 environment):
  PY="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python"
  export PYTHONPATH="$PWD/.gui-live-deps:$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn/python-ud3tn-utils:$HOME/CoAPoverBP-IPN-Draft05-NoProxy/vendor/aiocoap/src${PYTHONPATH:+:$PYTHONPATH}"
  "$PY" mission_control_v2_compact.py --live \
    --engine ~/CoAPoverBP-IPN-Draft05-NoProxy/applications/rover/NodeA_Mission_Draft05_Aggregation.py \
    --socket /tmp/ud3tn-ipn3-lab.aap2.sock --sol 42

Important:
  Keep rover_live_backend.py in the same GUI directory.
  Do not run two Rover GUI clients with the same AAP2 agent IDs concurrently.
  Your original mission_control_v2.py is not replaced.
