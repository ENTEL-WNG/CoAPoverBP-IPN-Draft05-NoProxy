# Installation and environment preparation — IETF 127, IPN allocator 974848

**Project:** Experimental direct CoAP over BPv7 (draft-ietf-core-coap-bp-05), three-component `ipn:` EIDs (RFC 9758), µD3TN/AAP2, **no CoAP-to-UDP proxy**.

This guide separates **Route A: the already-prepared, working three-VM laboratory** from **Route B: an independent checkout, which has not been validated end to end**. It documents the current allocator-`974848` configuration. Older repository material using allocator `0`, TCPCLv3 ports `4671–4673`, or the original Rover GUI is **historical and not interchangeable** with this setup.

> **Protect the live lab.** Do not switch Git branches, pull changes, reapply a patch, start a second GUI, restart µD3TN, replace contacts or alter AAP2 sockets on a VM currently running the demonstration. The updated scripts are committed to the GitHub branch `IPN_RFC_9758_Hackathon`, **not automatically installed on the running VMs**. Inspect and copy as needed into a separate test environment; coordinate any intentional restart with the lab owner.

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
./scripts/check_setup.sh
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

`ROVER_PY` remains a **legacy setting** for the older `scripts/rover_gui.sh`; **it is not the Python interpreter used by the current Experiment C GUI**. The newer GUI launcher uses the lab-specific interpreter:

```text
~/coapbp/experiments/draft05-ipn/workcopy/ud3tn/.venv-protoc-modern/bin/python
```

These directories and installed packages are **not delivered by cloning this repository**. On an independent machine, adapt the paths and install compatible dependencies before running a demo. The newer GUI launcher has its own hard-coded working-directory and interpreter paths; it has not been validated as portable to arbitrary machines.

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

**Do not use `./scripts/rover_gui.sh` for the latest demo**: it still launches the older `applications/rover/Rover_Mission_Control_Draft05_Aggregation.py`. Do not start a second Mission Control GUI while the existing one is active. A two-message aggregate must be **observed in Wireshark**, not assumed from two button clicks.

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

## Route B — Prepare an independent checkout (not validated end to end)

### 1. Obtain the correct original µD3TN source snapshot

This repository supplies a **nine-file µD3TN patch**, not a complete patched µD3TN checkout. The recorded base source revision is:

```text
37b968d5742cbd75292b534f3421fac70acc46b7
```

The matching original source repository's remote URL still needs confirmation. In a **separate clone/worktree**, after obtaining that exact source:

```bash
cd /path/to/original-CoAPoverBP-no-proxy-version
git checkout 37b968d5742cbd75292b534f3421fac70acc46b7
git apply --check /path/to/CoAPoverBP-IPN-Draft05-NoProxy/patches/ud3tn/ipn-three-component-aap2.patch
git apply /path/to/CoAPoverBP-IPN-Draft05-NoProxy/patches/ud3tn/ipn-three-component-aap2.patch
```

Apply the patch at the **top level of the original source tree**, because its paths include `ud3tn/`. Do not reapply it to the already patched live environment or assume it works on another µD3TN revision.

### 2. Build patched µD3TN

```bash
cd /path/to/original-CoAPoverBP-no-proxy-version/ud3tn
make posix
./build/posix/ud3tn --help
```

Build dependencies, source compatibility and clean-VM behavior are **not yet fully specified or independently validated**. Do not assume a stock µD3TN package supports this prototype's exact three-component IPN encoding.

### 3. Prepare compatible Python environments

The prepared lab used multiple existing Python environments (including an Earth Python 3.10 app environment, separate routing/AAP2 tools and the Rover GUI's `.venv-protoc-modern`). Their complete dependency lockfiles are **not committed**. The following illustrate preparation **only**, and are not a complete, tested install recipe:

```bash
python3 -m venv "$HOME/ipn-routing-venv"
"$HOME/ipn-routing-venv/bin/python" -m pip install --upgrade pip
"$HOME/ipn-routing-venv/bin/python" -m pip install 'protobuf==5.27.2' cbor2

python3 -m venv "$HOME/ipn-app-venv"
"$HOME/ipn-app-venv/bin/python" -m pip install --upgrade pip
"$HOME/ipn-app-venv/bin/python" -m pip install -e /path/to/CoAPoverBP-IPN-Draft05-NoProxy/vendor/aiocoap
"$HOME/ipn-app-venv/bin/python" -m pip install 'protobuf==5.27.2' cbor2 Pillow
```

Other packages, compatible source trees and correct Python module paths may still be required, including `ud3tn_utils`, `aioconsole` and GUI dependencies. Verify the specific versions in the successful lab environment rather than treating these examples as a dependency lock. A fresh checkout does **not** automatically provide the custom patched sources, installed Python packages, GUI background assets, or persistent application state.

### 4. Run non-destructive checks and document limitations

On the independent test copy, after configuring local paths:

```bash
cd /path/to/CoAPoverBP-IPN-Draft05-NoProxy
export UD3TN_ROOT=/path/to/original-CoAPoverBP-no-proxy-version/ud3tn
export CONFIG_PY="$HOME/ipn-routing-venv/bin/python"
export EARTH_PY="$HOME/ipn-app-venv/bin/python"
./scripts/check_setup.sh
```

If `check_setup.sh` reports OK, it only confirms **file presence**, not that an AAP2 registration, TCPCL connection, route, CoAP request, response Token matching, or full GUI demonstration works. A complete clean-clone installation and end-to-end replay have **not been demonstrated**.

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


