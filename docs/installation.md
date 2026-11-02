# Installation and environment preparation

This document distinguishes **the known working three-VM laboratory setup** from **a new checkout**, which has **not yet been validated end to end**. Commands were reconstructed from the successful Rover, Satellite and Earth runs and the version-controlled artifacts in this repository. They are not a claim that any arbitrary µD3TN revision supports the three-component IPN format.

## Hardware, topology and component roles

Three Ubuntu VMs (originally Ubuntu 20.04 series under VirtualBox) share an **internal** `enp0s8` network, with NAT on `enp0s3` for package installation. Assign static internal IPs:

| VM | IPv4 (`enp0s8`) | Node EID | TCPCLv3 | AAP2 Unix socket |
| --- | --- | --- | ---: | --- |
| Rover | `192.168.100.3` | `ipn:0.1.0` | 4671 | `/tmp/ud3tn-ipn3-lab.aap2.sock` |
| Satellite | `192.168.100.2` | `ipn:0.2.0` | 4672 | `/tmp/ud3tn-ipn3-sat.aap2.sock` |
| Earth | `192.168.100.1` | `ipn:0.3.0` | 4673 | `/tmp/ud3tn-ipn3-earth.aap2.sock` |

Application endpoint EIDs: Safety **`ipn:0.1.10`**, Science **`ipn:0.1.11`**, Earth CoAP server **`ipn:0.3.64`**. Check connectivity before launching:

```bash
ip -4 addr show enp0s8
ping -c 2 192.168.100.2  # example from Rover
```

The lab uses **IPN-only** endpoints and `coap://64.3.0.ipn.alt/...`. Do not switch to `dtn:` EIDs or a proxy in this Draft-05 test series.

## Route A: Reuse the existing tested three-VM lab

On each VM, clone or update the private GitHub repository where you are authorized to access it:

```bash
git clone https://github.com/ENTEL-WNG/CoAPoverBP-IPN-Draft05-NoProxy.git
cd CoAPoverBP-IPN-Draft05-NoProxy
./scripts/check_setup.sh
```

The **experiment binaries and old Python virtual environments are external to this Git repository**. The scripts default to the verified existing paths:

```text
UD3TN_ROOT   ~/coapbp/experiments/draft05-ipn/workcopy/ud3tn
CONFIG_PY    ~/coapbp/experiments/draft05-ipn/.venv-ipn/bin/python
ROVER_PY     ~/coapbp/CoAPoverBP-no-proxy-version/ud3tn/.venv-app/bin/python
EARTH_PY     ~/coapbp/experiments/draft05-ipn/.venv-coap310/bin/python
```

Override these paths if your checkout is elsewhere; for example:

```bash
export UD3TN_ROOT="$HOME/my-ipn-source/ud3tn"
export CONFIG_PY="$HOME/my-routing-env/bin/python"
export ROVER_PY="$HOME/my-rover-env/bin/python"
export EARTH_PY="$HOME/my-earth-env/bin/python"
```

Set the overrides **in every terminal** where you launch a script (or put them in a local, untracked shell configuration). They are *not* Git-tracked settings. The scripts add `vendor/aiocoap/src`, µD3TN's `python-ud3tn-utils`, and `pyd3tn` to Python's import path.

Follow [docs/ietf-demo.md](ietf-demo.md) for the exact daemon→contact→server→GUI→Wireshark sequence. **Do not stop already-running daemon processes just to test the scripts.** New daemons on the same sockets/ports would conflict with the live experiment.

## Route B: Prepare an independent checkout (not yet validated)

### 1. Obtain the correct µD3TN source snapshot

The repository contains a **nine-file patch**, not the complete µD3TN source tree. Obtain the original `CoAPoverBP-no-proxy-version` source repository (remote URL must be confirmed with the maintainers), check out the recorded **base commit**, and apply the patch **at the top-level of that source tree**, because the diff paths begin with `ud3tn/`:

```bash
cd /path/to/original-CoAPoverBP-no-proxy-version

git checkout 37b968d5742cbd75292b534f3421fac70acc46b7

git apply --check /path/to/CoAPoverBP-IPN-Draft05-NoProxy/patches/ud3tn/ipn-three-component-aap2.patch

git apply /path/to/CoAPoverBP-IPN-Draft05-NoProxy/patches/ud3tn/ipn-three-component-aap2.patch
```

Use an **independent clone/worktree**. Never apply the patch again to the already-modified live lab checkout. The patch's base/index checks were verified in the lab; applying it to a different upstream revision is not supported.

### 2. Build the patched µD3TN C implementation

The known source layout uses `ud3tn/build/posix/ud3tn`. Its POSIX build target is:

```bash
cd /path/to/original-CoAPoverBP-no-proxy-version/ud3tn
make posix
./build/posix/ud3tn --help
```

If build dependencies or headers are missing, use the instructions associated with **that exact source revision**. Dependencies and operating-system compatibility have not been resolved in a clean-VM build of this project. Do not substitute a stock µD3TN binary: it might encode/parse IPN EIDs differently.

### 3. Python environments

The working lab used a Python 3.8 routing/AAP2 environment (with **protobuf 5.27.2** and `cbor2`), an Earth Python 3.10 application environment, and a Rover GUI environment that includes Pillow. Those specific installed environments and their complete package lock files were **not** committed. A possible starting point on compatible VMs is:

```bash
python3 -m venv "$HOME/ipn-routing-venv"
"$HOME/ipn-routing-venv/bin/python" -m pip install --upgrade pip
"$HOME/ipn-routing-venv/bin/python" -m pip install 'protobuf==5.27.2' cbor2
```

For Rover/Earth application environments, install the pinned aiocoap tree **from this repository** using the packaging metadata (test compatibility with the chosen Python version) and add Pillow for the Rover GUI:

```bash
python3 -m venv "$HOME/ipn-app-venv"
"$HOME/ipn-app-venv/bin/python" -m pip install --upgrade pip
"$HOME/ipn-app-venv/bin/python" -m pip install -e /path/to/CoAPoverBP-IPN-Draft05-NoProxy/vendor/aiocoap
"$HOME/ipn-app-venv/bin/python" -m pip install 'protobuf==5.27.2' cbor2 Pillow
```

**These are preparation examples, not a validated dependency lock.** Check `vendor/aiocoap/pyproject.toml`, and preserve the exact versions successfully installed before declaring a fresh clone reproducible. Do not modify the current working `.venv-app`, `.venv-ipn`, or `.venv-coap310` environments in place.

### 4. Run checks and set script overrides

```bash
cd /path/to/CoAPoverBP-IPN-Draft05-NoProxy
export UD3TN_ROOT=/path/to/original-CoAPoverBP-no-proxy-version/ud3tn
export CONFIG_PY="$HOME/ipn-routing-venv/bin/python"
export ROVER_PY="$HOME/ipn-app-venv/bin/python"  # Rover VM
export EARTH_PY="$HOME/ipn-app-venv/bin/python"  # Earth VM
./scripts/check_setup.sh
```

**Remaining portability blockers:** The GUI also references an external `BASE` asset directory for its rover image; its relevant asset was not part of the initial source commit. Local MID state and Earth mission database paths remain lab-specific by design (files themselves must not enter Git). Verify/create appropriate paths when testing an independent VM. A complete clean-clone install and end-to-end replay have **not** been run.

## Security and troubleshooting

- In the successful logs µD3TN warned that AAP2 BDM functions had **no secret**; use **isolated test networks only**, not public interfaces. Review secret protection before external deployment.
- If AAP2 routes work initially but requests stop flowing, renew all **four direction-specific one-hour contacts**. Verify TCPCL handshakes and routing entries, not just client registration.
- If Earth replies but Rover receives nothing, check **both return contact routes**, Rover receive registration and Token correlations.
- Use TCP port **4673** to decode TCPCLv3 traffic on **Earth**, not 4763.
- In Wireshark, the BPv7 capture packet row can show a **67-byte TCP segment** because the **556-byte application payload is reconstructed across segments**. The BPv7 `Payload-Size` field is the relevant comparison.
- The Lua decoder is experimental. Save `.pcapng` and original terminal logs before interpreting fields.
