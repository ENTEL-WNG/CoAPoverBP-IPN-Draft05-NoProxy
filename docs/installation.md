# Installation and environment preparation — IETF 127, IPN allocator 974848

**Project:** Experimental direct CoAP over BPv7 (draft-ietf-core-coap-bp-05), three-component `ipn:` EIDs (RFC 9758), µD3TN/AAP2, **no CoAP-to-UDP proxy**.

This guide separates **Route A: the already-prepared, working three-VM laboratory** from **Route B: an independent checkout, which has not been validated end to end**. It documents the current allocator-`974848` configuration. Older repository material using allocator `0`, TCPCLv3 ports `4671–4673`, or the original Rover GUI is **historical and not interchangeable** with this setup.

> **Protect the live lab.** Do not switch Git branches, pull changes, reapply a patch, start a second GUI, restart µD3TN, replace contacts or alter AAP2 sockets on a VM currently running the demonstration. The updated scripts are committed to the GitHub branch `IPN_RFC_9758_Hackathon`, **not automatically installed on the running VMs**. Inspect and copy as needed into a separate test environment; coordinate any intentional restart with the lab owner.

For the step-by-step PDF, see the [Participant Handbook](../Participant%20Handbook/IETF127_CoAP_over_BPv7_Participant_Lab_Manual.pdf).

## Hardware, topology and component roles

The demonstrated environment uses three Ubuntu 20.04-series VMs in Oracle VirtualBox. `enp0s8` is the **internal network**, while `enp0s3` provides NAT connectivity where configured.

| VM | IPv4 on `enp0s8` | RFC 9758 node EID | TCPCLv3 port | AAP2 Unix socket |
| --- | --- | --- | ---: | --- |
| Rover | `192.168.100.3` | `ipn:974848.1.0` | `4771` | `/tmp/ud3tn-974848-rover.aap2.sock` |
| Satellite | `192.168.100.2` | `ipn:974848.2.0` | `4772` | `/tmp/ud3tn-974848-sat.aap2.sock` |
| Earth | `192.168.100.1` | `ipn:974848.3.0` | `4773` | `/tmp/ud3tn-974848-earth.aap2.sock` |

**Application endpoints:** Rover Safety `ipn:974848.1.10`; Rover Science `ipn:974848.1.11`; Earth CoAP server `ipn:974848.3.64`. The Satellite forwards **BPv7 bundles**, not CoAP/UDP packets as a proxy.

CoAP application URI examples:

- Safety: `coap://64.3.974848.ipn.alt/mission/safety-guidance`
- Science: `coap://64.3.974848.ipn.alt/science/observations`

The `.ipn.alt` authority is mapped by the application to the **Earth CoAP service EID** (`ipn:974848.3.64`), not the bare Earth node EID. Only the three-component `ipn:` scheme is in scope; do not substitute `dtn:` EIDs.

On the relevant VM, these **read-only** checks help confirm the setup:

```bash
ip -4 addr show enp0s8
ping -c 2 192.168.100.2  # Example from Rover or Earth
ps -eo pid,args | grep -E '[u]d3tn|[m]ission_control_v2|[N]odeB_Mission'
```

Also check time synchronization (for example, `chronyc tracking`). Large clock differences can cause BPv7 bundles to expire unexpectedly.

## Route A — Reuse the prepared three-VM lab (preferred for the demo)

### 1. Confirm the correct source and branch, without changing the live lab

The **current** scripts and documentation are on the GitHub branch `IPN_RFC_9758_Hackathon`. A default `git clone` will normally check out `main`, which may still contain older configuration. For an **independent copy only** (not inside the active lab checkout):

```bash
git clone --branch IPN_RFC_9758_Hackathon \
  https://github.com/ENTEL-WNG/CoAPoverBP-IPN-Draft05-NoProxy.git
cd CoAPoverBP-IPN-Draft05-NoProxy
git branch --show-current
bash scripts/check_setup.sh
```

If the repository already exists on an active Rover/Earth/Satellite VM, **do not run `git pull`, `git switch`, or the clone command over that working directory**. The live Rover was observed on a local `main` revision while successfully using its own already-configured Experiment C GUI; that is not a reason to change it during the Hackathon.

`check_setup.sh` is read-only and checks for repository files plus selected local binaries/environments. It does **not** establish successful routing, dependencies, or end-to-end CoAP/BPv7 communication. It may report missing items in a fresh clone, because the patched µD3TN binary and Python environments are external.

### 2. Local paths and Python environments

The shared helper `scripts/common.sh` currently defaults to:

```text
UD3TN_ROOT  = ~/coapbp/experiments/draft05-ipn/workcopy/ud3tn
CONFIG_PY   = ~/coapbp/experiments/draft05-ipn/.venv-ipn/bin/python
EARTH_PY    = ~/coapbp/experiments/draft05-ipn/.venv-coap310/bin/python
ROVER_PY    = ~/coapbp/CoAPoverBP-no-proxy-version/ud3tn/.venv-app/bin/python
```

These `common.sh` paths are **fallbacks for the previously prepared laboratory**, not recommended paths for a new participant VM. `ROVER_PY` is an older environment variable and does **not** select the interpreter for the current Mission Control launcher.

The current `scripts/rover_gui.sh` is a wrapper around `gui-v2/IETF127_Experiment_C_Package/run_gui_congestion_results.sh`. That launcher locates the GUI and Rover engine relative to the repository and chooses Python from `ROVER_GUI_PY`, the repository's `.venv`, or a preconfigured lab environment. It is **not** a complete installer: patched µD3TN, Python dependencies, AAP2 sockets, contacts and the Earth server must be prepared separately.

For **new participant VMs**, follow Route B and source `scripts/participant_env.sh` in each terminal to set `UD3TN_ROOT`, `CONFIG_PY`, `EARTH_PY` and `ROVER_GUI_PY` to the separately prepared installation. Do not replace the working laboratory's Python environments.

For launch helpers based on `common.sh`, environment overrides can be set in the terminal where they will run, for example:

```bash
export UD3TN_ROOT="$HOME/path/to/patched/ud3tn"
export CONFIG_PY="$HOME/path/to/routing-venv/bin/python"
export EARTH_PY="$HOME/path/to/earth-venv/bin/python"
```

Do **not** overwrite the prepared, working virtual environments simply to match these examples.

### 3. Confirm existing services first; start new services only in an idle lab

Use the read-only process check above. **If µD3TN, Earth NodeB or the Rover Mission Control GUI is already running, reuse the existing instance.** Do not invoke the launch commands below on already-occupied sockets/ports.

For a *fresh, prepared and authorized* three-VM session, `scripts/start_ud3tn.sh` selects the following settings:

| Execute on | Command from repository root | Expected node and port |
| --- | --- | --- |
| Rover | `./scripts/start_ud3tn.sh rover` | `ipn:974848.1.0`, `4771` |
| Satellite | `./scripts/start_ud3tn.sh satellite` | `ipn:974848.2.0`, `4772` |
| Earth | `./scripts/start_ud3tn.sh earth` | `ipn:974848.3.0`, `4773` |

Each starts a long-lived patched µD3TN process. **Do not run one while the equivalent daemon is already active.** The script checks for the binary at `$UD3TN_ROOT/build/posix/ud3tn`; it does not build it for you.

### 4. Configure contacts only for a fresh session

The following scripts use AAP2 to configure four forwarding directions, with 3,600-second scheduled contacts and a 100,000-byte volume parameter:

| Run on | Command | Routes established |
| --- | --- | --- |
| Satellite | `./scripts/satellite_contacts.sh` | Satellite → Earth; Satellite → Rover |
| Earth | `./scripts/earth_contacts.sh` | Earth → Satellite; reachability toward Rover |
| Rover | `./scripts/rover_contacts.sh` | Rover → Satellite; reachability toward Earth |

All three scripts have been updated on the Hackathon branch for allocator `974848` and ports `4771–4773`. They create ordinary one-hour contacts, **not a complete automatic ON/OFF contact experiment**. Do not reconfigure them during an active GUI-managed ON/OFF run unless the person operating the testbed directs you to. A successful configuration command is not proof that a bundle reached Earth.

### 5. Earth CoAP application

The **running Earth server identified in the prepared lab** was:

```text
~/coapbp/experiments/draft05-ipn/NodeB_Mission_Draft05_IPN_Allocator974848.py
```

A copy of this allocator-974848 server is committed on the Hackathon branch as:

```text
applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py
```

In a **fresh, idle, configured Earth environment**, the updated launcher is:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_server.sh
```

It uses `$EARTH_PY` and connects to `/tmp/ud3tn-974848-earth.aap2.sock` as the CoAP application service 64. **Do not launch the copy while the original Earth server is already running.** The original `applications/earth/NodeB_Mission_Draft05_IPN.py` remains as historical code and uses older addresses.

### 6. Rover Experiment C Mission Control GUI

The **verified launch route on the prepared Rover VM** is:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This runs `mission_control_v2_live_metrics.py`, using:

- Rover engine: `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py`;
- Rover AAP2 socket: `/tmp/ud3tn-974848-rover.aap2.sock`;
- Live metrics under the repository's `Results/raw/` directory;
- Initial **NSTART=1**, with explicit GUI controls for a **controlled, experimental NSTART=2** mode.

The optional `bash scripts/rover_gui.sh` helper now launches the **same current Experiment C GUI**. The demonstrated command remains `bash ./run_gui_congestion_results.sh` from the GUI folder. Do not start a second Mission Control GUI while one is active. A two-message aggregate must be **observed in Wireshark**, not assumed from two button clicks.

### 7. Inspect bundles with Wireshark on Earth

The current lab used **Wireshark 4.6.9** with native RFC 9758 decoding of three-component BPv7 EIDs. The separate Lua script `wireshark/coapbp05_ipn64_PL65000.lua` decodes experimental CoAP Single/Aggregate payload fields.

- Install that Lua file in the **Personal Lua Plugins** directory shown by **Help → About Wireshark → Folders** for the exact Wireshark installation. Restart Wireshark after installation.
- With a **native** Wireshark installation and capture permission, capture directly from `enp0s8` on Earth. The current TCPCLv3 port is **4773** (not 4673).
- The **Flatpak** Wireshark build may not expose the host's interfaces. On the prepared Earth VM, the repository provides a helper that opens Wireshark with live capture:

  ```bash
  cd ~/CoAPoverBP-IPN-Draft05-NoProxy
  bash wireshark/wireshark-ipn-live.sh enp0s8
  ```

  The helper uses host `tcpdump` internally to feed a pipe; you do **not** have to type `tcpdump` separately. It may ask for `sudo`. The VM-specific shortcut `~/bin/wireshark-ipn-live` is not automatically installed on other machines. Do not disrupt µD3TN to troubleshoot Wireshark.

Useful **display filters**, entered one at a time:

```text
bpv7
tcp.port == 4773
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 2
```

Use **Analyze → Decode As** if a TCPCLv3 conversation is not decoded automatically. Save `.pcapng` traces with the experiment, node, date and NSTART mode. For full setup and decoding instructions, see [Wireshark README](../wireshark/README.md) and [IETF demo guide](ietf-demo.md).

### 8. Evidence and what has actually been shown

The updated [Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) documents allocator-974848 functional results, including a **59-byte Single Safety GET**, **102-byte Single Science POST**, and **212-byte Science Aggregate** with two POST members of 50-byte Payload-length each and separately matched responses in the documented test. A captured BPv7 lifetime of **90,000 ms** and three-element EID decoding were also documented.

The repository contains `evidence/Earth_IPN974848_Single_and_Aggregate.pcapng`, and `scripts/check_setup.sh` references that current evidence file. Do **not** assume that frame numbers from Experiment C screenshots or older captures match this `.pcapng` without checking. **Earlier allocator-0 experiments** with a **556-byte Science Aggregate** or **116-byte Safety Aggregate** belong to a different configuration and must not be mixed with the newer results.

## Route B — Prepare independent participant VMs (not yet validated end to end)

These steps use the **actual setup scripts on this Hackathon branch**. Run them only on three **new participant Ubuntu VMs**, never on the active Rover/Satellite/Earth demonstration. The scripts provide reproducible *preparation steps*, not a fully tested automatic deployment.

### 1. Create and configure the three VMs

In VirtualBox, create **three Ubuntu VMs**, each with Adapter 1 set to NAT and Adapter 2 set to **Internal Network** named exactly `intnet`. The internal Linux interface is usually `enp0s8` (check with `ip -br addr`). All three VMs must use the same `intnet` name.

| VM | Role | Internal IPv4 | Node EID | TCPCLv3 |
| --- | --- | --- | --- | ---: |
| Rover | CoAP Safety and Science client + GUI | `192.168.100.3/24` | `ipn:974848.1.0` | `4771` |
| Satellite | BPv7 relay | `192.168.100.2/24` | `ipn:974848.2.0` | `4772` |
| Earth | CoAP server + Wireshark | `192.168.100.1/24` | `ipn:974848.3.0` | `4773` |

### 2. Install prerequisites, then clone the correct branch on EACH new VM

**On each new Ubuntu participant VM**, first install Git and the build and network utilities before attempting `git clone`:

```bash
sudo apt update
sudo apt install -y git build-essential libsqlite3-dev \
  python3-venv python3-pip python3-tk iproute2 iputils-ping
python3 --version
```

The live Python helper requires **Python 3.10 or newer**, with matching Tkinter and `venv` support. Ubuntu 20.04's default Python is older; for that release, provision a **separate Python 3.10+ interpreter** and set `PYTHON_BIN` if needed. Do not modify the working demonstration VMs or their Python environments. Other µD3TN build prerequisites can vary by Ubuntu version.

**After Git is installed**, clone the correct Hackathon branch:

```bash
git clone --branch IPN_RFC_9758_Hackathon \
  https://github.com/ENTEL-WNG/CoAPoverBP-IPN-Draft05-NoProxy.git
cd CoAPoverBP-IPN-Draft05-NoProxy
git branch --show-current
```

The branch should print `IPN_RFC_9758_Hackathon`. The repository's default branch is `main`, which is not the target for this guide.

### 3. Prepare a separate patched µD3TN tree on EACH new VM

Run from the Hackathon repository root:

```bash
bash scripts/prepare_participant_ud3tn.sh --check
bash scripts/prepare_participant_ud3tn.sh
```

This script clones `https://github.com/ENTEL-WNG/CoAPoverBP-no-proxy-version.git` at the pinned public revision `a2fb4311b89b31c30e93a5c1704f78131594e927`, checks/applies the nine-file three-component IPN patch **inside a separate directory**, and attempts `make posix -j2`. Its expected binary location is:

```text
~/ietf127-participant/CoAPoverBP-no-proxy-version/ud3tn/build/posix/ud3tn
```

All nine patch input file hashes were checked against the public source. **A fresh independent compilation and live integration test have not been completed.** Do not reapply the patch to an active µD3TN workcopy.

### 4. Prepare Python on EACH new VM

```bash
export UD3TN_ROOT="$HOME/ietf127-participant/CoAPoverBP-no-proxy-version/ud3tn"
bash scripts/setup_participant_python.sh --live
source scripts/participant_env.sh
```

The setup script creates the repository's `.venv` and installs the live Python packages. It now pins **`protobuf==5.28.3`**, consistent with the checked-in generated AAP2 bindings in the pinned source. It uses **modified vendored aiocoap**, not stock PyPI aiocoap. `participant_env.sh` exports `UD3TN_ROOT`, `CONFIG_PY`, `EARTH_PY`, `ROVER_PY`, `ROVER_GUI_PY` and `PYTHONPATH` for that terminal. Re-run `source scripts/participant_env.sh` in each new terminal.

You can optionally prepare a **GUI-only simulated demo** without µD3TN:

```bash
bash scripts/setup_participant_python.sh --demo
cd gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh --demo
```

Simulated activity must **not** be reported as actual bundle-delivery evidence.

### 5. Verify and, if necessary, configure networking on EACH fresh VM

Check the VM's own role, for example on Rover:

```bash
bash scripts/participant_vm_network.sh --check rover
```

On Satellite use `satellite`, and on Earth use `earth`. Only on a **new participant VM** that does not already have an assigned internal IPv4 address, and only after verifying Adapter 2 is `intnet`, use:

```bash
IETF127_FRESH_VM=YES bash scripts/participant_vm_network.sh --configure rover
```

Replace `rover` with the actual VM role. `--configure` changes the IP address **temporarily until reboot**. When all three addresses are configured, check peer reachability using `ping -c 2 192.168.100.2` from Rover/Earth and the other peer addresses as appropriate. Also check that VM clocks are reasonably synchronized.

### 6. Start the three µD3TN nodes on FRESH, IDLE VMs

On each VM, in its **own long-lived terminal**, enter the Hackathon repository root, then:

```bash
source scripts/participant_env.sh
```

Run the correct command, one per VM:

```text
SATELLITE: bash scripts/start_ud3tn.sh satellite
EARTH:     bash scripts/start_ud3tn.sh earth
ROVER:     bash scripts/start_ud3tn.sh rover
```

Keep each µD3TN terminal open. **Never start another µD3TN instance if the socket/port is already in use.**

### 7. Configure the BP forwarding contacts

Open a **second terminal on each VM**; change into the Hackathon repository root and run `source scripts/participant_env.sh` again. Then execute:

```text
SATELLITE: bash scripts/satellite_contacts.sh
EARTH:     bash scripts/earth_contacts.sh
ROVER:     bash scripts/rover_contacts.sh
```

These scripts use **allocator `974848`, TCPCLv3 ports `4771–4773`, and scheduled 3,600-second contacts**. The Satellite forwards bundles both directions; it is not a CoAP proxy. These ordinary contact scripts do **not** themselves implement the ON/OFF exercise, and contacts can expire.

### 8. Start the Earth CoAP server

In a **third Earth terminal**, from the repository root:

```bash
source scripts/participant_env.sh
bash scripts/earth_server.sh
```

This starts `applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py` as service `ipn:974848.3.64` using Earth AAP2 socket `/tmp/ud3tn-974848-earth.aap2.sock`. Do not run two Earth CoAP servers with the same agent ID.

### 9. Open the SAME real Rover Mission Control GUI

On Rover, in a new terminal:

```bash
source scripts/participant_env.sh
cd gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This familiar command runs the **real live** `mission_control_v2_live_metrics.py` and `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py`; it does **not** fall back to simulated demo mode. The launcher supports a repository-local `.venv` or an explicit `ROVER_GUI_PY`, and locates the engine relative to the repository. A correctly installed patched µD3TN, Rover AAP2 socket, Earth server, valid contacts and dependencies are still required.

Start with a Single Safety GET or Science POST. For the experimental two-request Science Aggregate use the guarded NSTART controls and validate that **one BPv7 request bundle** contains two distinct CoAP members; do not infer aggregation solely from GUI button clicks.

### 10. Capture evidence with Wireshark on Earth

With a native Wireshark installation and host capture permission, capture directly on Earth `enp0s8`. For the repository's Flatpak helper (requires Flatpak Wireshark and host tcpdump), from the repository root run:

```bash
bash wireshark/wireshark-ipn-live.sh enp0s8
```

Install `wireshark/coapbp05_ipn64_PL65000.lua` in the **Personal Lua Plugins** directory shown by Wireshark's **Help → About Wireshark → Folders**, then restart Wireshark. Useful display filters include `tcp.port == 4773`, `bpv7`, `bpv7.eid.ipn_alloc == 974848`, and `coapbp05.count == 2`. Save `.pcapng` files and correlate observed request/response Tokens against the current-run Rover/Earth logs.

### 11. Check installation status and record limitations

From the repository root, after sourcing the participant environment:

```bash
bash scripts/check_setup.sh
```

This script checks **presence of files**, not end-to-end success. Some role-specific checks still assume legacy lab paths; interpret any such result against the actual participant environment rather than modifying working machines.

**The complete three-VM fresh-install workflow has not been independently validated.** Report build errors, contact failures, missed responses and absent captures as actual observations. Preserve the original active demonstration lab unchanged.

## Security and troubleshooting

- **Lab safety:** The testbed has previously run with AAP2 BDM functions reporting no configured secret. Use **isolated, trusted laboratory networks only**; do not expose these defaults to the Internet.
- **Contact expiry:** The four direction-specific configured contacts are scheduled for one hour. Check remaining contact state and routes before deciding to renew; don't overwrite an intentional GUI ON/OFF experiment.
- **Return path:** Earth response bundles must travel through Satellite toward Rover. Check Earth→Satellite and Satellite→Rover routes, application registrations and response Tokens if Rover has no matched response.
- **Correct capture port:** On Earth, use TCPCLv3 port **4773**, not the historical `4673` or a mistaken `4763`. TCP packet lengths are not the same as BPv7 application payload lengths.
- **Clock differences:** Investigate VM time synchronization and bundle creation/lifetime if bundles disappear or are discarded as expired.
- **No forced restarts:** Do not kill µD3TN or the live GUI to fix missing Wireshark interfaces or missing metrics; use read-only inspection first.
- **Evidence:** Save corresponding `.pcapng` and application logs for important runs. Distinguish submission to local µD3TN, arrival at Earth, and confirmed response reception at Rover.
- **Protocol status:** The Lua dissector and local aiocoap's Payload-length option number `65000` are experimental. Controlled NSTART=2 tests are **not** proof of cross-application congestion safety or complete draft-05 conformance.

For the step-by-step demonstration, see [IETF 127 demo guide](ietf-demo.md). For current and historical results, see [Experiment C](../experiments/Experiment_C_Updated_IPN974848/README.md).



