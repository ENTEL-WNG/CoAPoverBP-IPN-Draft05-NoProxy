# Source collection checklist (do not push until complete)

Your active code is stored in **three different VirtualBox VMs**, whereas GitHub stores one repository. Work in a separate `~/CoAPoverBP-IPN-Draft05-NoProxy` checkout on **Rover**. Copy from your live running files; **do not move or edit originals**.

## Rover application files

From Rover VM, assuming the ZIP was unpacked into `~/CoAPoverBP-IPN-Draft05-NoProxy`:

```bash
REPO="$HOME/CoAPoverBP-IPN-Draft05-NoProxy"
BASE="$HOME/coapbp/experiments/draft05-ipn"
cp -v "$BASE/NodeA_Mission_Draft05_Aggregation.py" "$REPO/applications/rover/"
cp -v "$BASE/Rover_Mission_Control_Draft05_Aggregation.py" "$REPO/applications/rover/"
python3 -m py_compile "$REPO/applications/rover/"*.py
```

Optional, clearly mark the previous IPN versions as history:

```bash
OLD="$HOME/coapbp/experiments/ipn-hackathon-2026"
cp -v "$OLD/coap-working-copies/NodeA_Mission_Draft05.py" "$REPO/applications/rover/history/"
cp -v "$OLD/Rover_Mission_Control_Draft05_IPN.py" "$REPO/applications/rover/history/" 2>/dev/null || true
```

These source files contain absolute path assumptions (`ENGINE`, AAP2 sockets, other assets); simply collecting them is **not** a portable working deployment. Document adjustments before claiming reproducibility.

## Earth server

On Earth, confirm its live file:

```bash
ls -l ~/coapbp/experiments/draft05-ipn/NodeB_Mission_Draft05_IPN.py
```

If SSH works from Rover to Earth, copy the Earth file **from Rover**:

```bash
scp mahi@192.168.100.1:~/coapbp/experiments/draft05-ipn/NodeB_Mission_Draft05_IPN.py \
  "$REPO/applications/earth/"
```

If SSH is unavailable, use a VirtualBox shared folder or transfer the Earth file another way. Check copied file against the running version.

## Modified µD3TN and aiocoap — essential

Do **not** assume a standalone `eid.c` is all the µD3TN changes. The modified C build, associated headers, AAP2 Python utilities, config/routing tools, and aiocoap fork are required.

First inspect the actual live checkouts on **each relevant VM**:

```bash
UD="$HOME/coapbp/experiments/draft05-ipn/workcopy/ud3tn"
git -C "$UD" status --short
(git -C "$UD" remote -v || true)
(git -C "$UD" rev-parse HEAD || true)
```

For aiocoap, determine the live version/path and git status:

```bash
find "$HOME/coapbp" -path '*/aiocoap/src/aiocoap/numbers/optionnumbers.py' -print
```

Record the exact upstream base revision, all locally changed files and licenses. If version-controlled, create reviewed `git diff` patches and include any untracked new source files. If not, create a clearly labeled source snapshot with provenance, avoiding embedded `.git`, build outputs, `.venv`, and socket/state artifacts. Verify a clean reproduction on another checkout **before** calling the repository complete.

## Evidence

Copy the actual November 1 .pcapng captures from Earth to `evidence/safety/` and `evidence/science/`. Add concise metadata mapping the captures to Rover and Earth terminal logs. A `.pcapng` can expose internal IP addresses and protocol payloads; review before publishing beyond your research group. Do not commit VM images, passwords, API tokens, private keys, runtime MID-state JSON, DB files or archives.

Finally inspect `git status --short`, `git diff --cached --stat`, and each staged file before committing and pushing.
