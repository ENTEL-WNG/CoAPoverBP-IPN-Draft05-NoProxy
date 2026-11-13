# IETF 127 Hackathon demonstration — CoAP over BPv7 Draft-05, three-component IPN, no proxy

**Audience:** IETF 127 Hackathon participants, project champions and supervisors  
**Scope:** Current three-VM laboratory setup using RFC 9758 three-component `ipn:` EIDs, **allocator `974848`**, and direct CoAP over BPv7 through µD3TN/AAP2. **No CoAP-to-UDP proxy** is used.

**Demo objective:** Show the Rover sending CoAP NON GET/POST requests through the Satellite BPv7 relay to Earth; inspect the RFC 9758 source/destination EIDs, independent CoAP Message IDs (MIDs) and Tokens, and—when aggregation is enabled—two CoAP requests in one BPv7 bundle with separate Earth responses.

> **Important:** This document distinguishes the **current allocator-974848 configuration** from **historical allocator-0 experiments**. Packet sizes, frame numbers and Tokens from older experiments must not be presented as current measurements. These commands describe the prepared laboratory, **not a proven clean-clone installation**. Do not restart or replace GUI-managed µD3TN daemons, contacts, sockets, or live application processes during a demonstration.

## 1. Architecture and preparation

| Node | VirtualBox interface and IP | Node EID | TCPCLv3 port | Application EID |
| --- | --- | --- | ---: | --- |
| Rover | `enp0s8` · `192.168.100.3` | `ipn:974848.1.0` | `4771` | Safety `ipn:974848.1.10`; Science `ipn:974848.1.11` |
| Satellite | `enp0s8` · `192.168.100.2` | `ipn:974848.2.0` | `4772` | BPv7 forwarding only; **no CoAP proxy** |
| Earth | `enp0s8` · `192.168.100.1` | `ipn:974848.3.0` | `4773` | CoAP server `ipn:974848.3.64` |

```text
Rover Safety  ipn:974848.1.10 ---\
                                   \    BPv7 / TCPCLv3
                                    > Rover -> Satellite -> Earth CoAP ipn:974848.3.64
                                   /    (no UDP proxy)
Rover Science ipn:974848.1.11 ---/
                         <--- separate BPv7 Single response bundles ---
```

- Safety URI: `coap://64.3.974848.ipn.alt/mission/safety-guidance`
- Science URI: `coap://64.3.974848.ipn.alt/science/observations`
- The Earth CoAP **application** EID is `ipn:974848.3.64`; the bare Earth **node** EID is `ipn:974848.3.0`.
- Confirm that all VMs can reach one another on the internal network, that their clocks are synchronized (`chronyc tracking` where available), and that patched µD3TN, required virtual environments and AAP2 sockets exist. Use the read-only `./scripts/check_setup.sh` to inspect file presence, remembering that it is **not** an end-to-end test.

### Preserve the already-running demonstration

Before opening another GUI or launching a daemon, inspect current processes on the relevant VM:

```bash
ps -eo pid,args | grep -E '[u]d3tn|[m]ission_control_v2|[N]odeB_Mission'
```

**If the relevant process is already running, reuse it; do not run another copy.** In particular, the latest Rover GUI can control contacts and maintain in-memory NodeA engines. Closing it or relaunching its supporting nodes can disrupt the experiment. When you need fresh contacts or an ON/OFF schedule, coordinate changes with the person controlling the live testbed.

## 2. Starting a fresh, non-running laboratory (only when authorized)

**Skip this section entirely if the three nodes and GUI are already active.** Run these commands only on a prepared lab with the required binaries/virtual environments. The startup scripts below have been updated on the `IPN_RFC_9758_Hackathon` branch for allocator `974848` and ports `4771–4773`.

From the root of the checked-out **Hackathon branch** on each named VM:

**Rover VM**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh rover
```

**Satellite VM**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh satellite
```

**Earth VM**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh earth
```

Each command stays running in its terminal. It uses patched µD3TN, the corresponding three-component node EID, the AAP2 Unix sockets beginning `/tmp/ud3tn-974848-`, and TCPCLv3 ports `4771`, `4772` and `4773`. A missing binary or an occupied socket/port must be investigated; **do not forcibly stop GUI-managed processes**.

## 3. Configure forwarding contacts (fresh lab only)

The contact scripts create time-limited contacts with a **3600-second** scheduled duration. Do **not** run them repeatedly during a live GUI-controlled ON/OFF experiment. In a fresh session, use separate terminals on the relevant VMs after their daemons are ready.

**Satellite — forward to both Earth and Rover**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/satellite_contacts.sh
```

**Earth — return traffic to Rover through Satellite**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_contacts.sh
```

**Rover — forward toward Earth through Satellite**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/rover_contacts.sh
```

The `*_contacts.sh` scripts above have been aligned with the current allocator-974848 topology on the Hackathon branch. A successful contact-configuration command does not prove forwarding: confirm contact/route activity and actual TCPCL/BPv7 traffic in the daemon logs and Wireshark.

## 4. Current Earth application and Rover Mission Control GUI

**Earth (only if the server is not already running):**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_server.sh
```

The updated launcher targets the copied working application:

`applications/earth/NodeB_Mission_Draft05_IPN_Allocator974848.py`

The verified Earth lab also runs this application from its original location under `~/coapbp/experiments/draft05-ipn/`. **Do not run both copies simultaneously.** Its AAP2 socket is `/tmp/ud3tn-974848-earth.aap2.sock`, with CoAP service EID `ipn:974848.3.64`.

**Rover: use the actual Experiment C Mission Control v2 launcher** (not the older `scripts/rover_gui.sh`):

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy/gui-v2/IETF127_Experiment_C_Package
bash ./run_gui_congestion_results.sh
```

This is the known working launch route on the prepared Rover VM. It runs `mission_control_v2_live_metrics.py` with the Experiment C engine `experiment_c_engine/NodeA_Mission_Draft05_Aggregation.py`, the Rover socket `/tmp/ud3tn-974848-rover.aap2.sock`, and live measurement output under `Results/raw/`. **It contains absolute paths specific to the prepared Rover VM and is not a portable one-command participant installation.** If the GUI is already open, keep using the existing instance.

The launcher starts with **NSTART=1**. The GUI's experimental controls can change to **NSTART=2** for an aggregation demonstration. Select the appropriate mode in the GUI and verify the actual logs/packets; **two clicks alone do not guarantee an Aggregate**. The aggregation buffer holds up to two messages with an approximately 10-second maximum delay in the tested implementation. NSTART=2 is an experimental setting, **not a congestion-safety proof**.

## 5. Capture and decode BPv7 traffic on Earth with Wireshark

The known lab used **Wireshark 4.6.9** with native RFC 9758 three-component EID decoding and the repository's separate experimental CoAP Lua dissector.

1. Install the existing file `wireshark/coapbp05_ipn64_PL65000.lua` in the **Personal Lua Plugins** directory shown under **Help → About Wireshark → Folders** for the *specific Wireshark installation*. Restart Wireshark. Do not assume the native Ubuntu and Flatpak plugin directories are the same.
2. On a **native** Wireshark installation with capture permissions, start a live capture on `enp0s8`. The relevant Earth TCPCL port is **4773** (not the historical port 4673). Optionally use capture filter `tcp port 4773`.
3. If the Earth installation uses **Flatpak Wireshark 4.6.9** and does not list capture interfaces, launch the existing repository helper from a terminal instead:

   ```bash
   cd ~/CoAPoverBP-IPN-Draft05-NoProxy
   bash wireshark/wireshark-ipn-live.sh enp0s8
   ```

   The helper performs host capture and supplies a named pipe to Wireshark. Participants need not run `tcpdump` manually; the helper uses it internally and may request `sudo`. A locally installed shortcut such as `~/bin/wireshark-ipn-live` may serve the same purpose on the prepared VM, but is **not assumed to exist on every participant machine**. Keep the helper terminal open during the capture.
4. If traffic appears only as undecoded TCP, use **Analyze → Decode As** for the actual TCPCLv3 connection/port, and ensure the capture includes enough packets for dissection/reassembly.
5. Apply these **Wireshark display filters** one at a time:

   ```text
   tcp.port == 4773
   bpv7
   bpv7.eid.ipn_count == 3
   bpv7.eid.ipn_alloc == 974848
   coapbp05.count == 1
   coapbp05.count == 2
   ```

6. Expand the BPv7 source/destination EIDs to show **IPN Element Count = 3**, allocator `974848`, node and service. In an Aggregate, expand the Lua-decoded **CoAP member #1 / #2**, MIDs, Tokens and Payload-length. Earth replies were demonstrated as **separate Single response bundles**, not one aggregated response bundle.
7. Save `.pcapng` evidence and correlate it with the matching Rover and Earth logs. A bundle observed arriving at Earth does not, by itself, prove Rover received its response.

See [`wireshark/README.md`](../wireshark/README.md) for the version-specific plugin and capture instructions.

## 6. Three participant exercises

| Exercise | Participant action | Evidence to collect |
| --- | --- | --- |
| **A. Single baseline** | Use the prepared GUI's Single/NSTART=1 mode and send a Safety NON GET or Science NON POST. | One request bundle; source/destination `ipn:974848.*.*`; absent Aggregate-specific Payload-length on a Single, request Token, corresponding Earth response and Rover match if observed. |
| **B. Two-request Aggregate** | In a controlled GUI aggregation mode that allows **NSTART=2**, send two requests from the **same Rover application EID** toward the same Earth EID, within the buffer window. | **One BPv7 request bundle with two CoAP members**, distinct MIDs/Tokens, Payload-length per member; Earth processes both and sends separate response bundles. Confirm via Wireshark and matching logs rather than assuming success from button clicks. |
| **C. ON/OFF link challenge** | With the lab owner's permission, use the **existing GUI contact controls** to introduce an OFF interval on Rover–Satellite or Satellite–Earth, then restore contact. Do not kill µD3TN or change VM network interfaces indiscriminately. | Time the OFF/ON intervals; note locally queued/submitted requests versus confirmed delivery; identify when the delayed bundle traverses the link; compare latency, contact state, missing/late replies and saved `.pcapng` evidence. |

**Discussion for participants:** What changes when Earth is unreachable? Can BPv7 preserve a request until a forwarding contact becomes available, subject to bundle lifetime and routing? Does aggregation reduce the number of request bundles? How does waiting for aggregation change latency and risk of exceeding a deadline? These are questions to investigate, **not outcomes to assume**.

## 7. Recorded proof from the current allocator-974848 experiment

The separately documented [updated Experiment C report](../experiments/Experiment_C_Updated_IPN974848/README.md) includes the following observations:

| Recorded test | Observed BPv7 application payload | Recorded outcome |
| --- | ---: | --- |
| Safety Single NON GET | **59 B** | **4/4** Token-matched `2.05 Content` responses in the documented test |
| Science Single NON POST | **102 B** | **1/1** Token-matched `2.01 Created` response |
| Science Aggregate: two NON POSTs | **212 B** | Two members, **50 B Payload-length per POST**; **2/2** Token-matched `2.01 Created` responses |

The documented current Science Aggregate used request MIDs `2543436` and `2543437` and Tokens `2f8ecb82` and `715deaac`. Wireshark screenshots from this configuration show allocator `974848` and three-element IPN EIDs; the Experiment C report also records a **90,000 ms** lifetime in frame **76** of one documented capture. **Frame numbers and data sizes vary by run and payload**: they are not fixed protocol values, and the Mission Control GUI may create Science JSON payloads of different sizes.

The repository also includes [`evidence/Earth_IPN974848_Single_and_Aggregate.pcapng`](../evidence/Earth_IPN974848_Single_and_Aggregate.pcapng). Use it as packet evidence and inspect its actual frame numbers rather than assuming the Experiment C screenshot numbering matches this file.

### Historical example — allocator 0 only (do not mix with the current run)

An **older** allocator-`0` Science Aggregate contained **556 B** of BPv7 application payload, with two `227 B` member payloads. Its packet walkthrough reported request frame **14**, response frames **31** and **49**, and Tokens `9fc152cf` / `5ae01fab`. Earlier Safety Aggregate evidence contained a **116 B** BPv7 application payload. Those values belong to **different historical captures** and are **not** expected values for the allocator-974848 demonstration. See [`docs/results.md`](results.md) for that historical experiment.

## 8. Suggested five-minute spoken demonstration

1. **30 seconds:** Present the three-node topology and explain that Satellite forwards BPv7 bundles, not CoAP/UDP proxy traffic.
2. **45 seconds:** Show `ipn:974848.1.11` → `ipn:974848.3.64` in Wireshark and point out the RFC 9758 allocator, node and service components.
3. **60 seconds:** Show the Mission Control v2 GUI and a verified Single exchange or a configured experimental Aggregate.
4. **90 seconds:** Open a current Aggregate trace (for example, the documented **212 B** Science Aggregate), expand both CoAP members and compare their MIDs, Tokens and Payload-length fields.
5. **45 seconds:** Show Earth's separate response bundles and any matching Rover response logs available from the same run.
6. **30 seconds:** Identify limitations: experimental option 65000; controlled NSTART=2 without demonstrated network-wide congestion safety; no aggregated responses; fresh-clone setup not fully validated.

For prerecorded material, use the project [`Hackathon_Media`](../Hackathon_Media/) folder. Confirm which video corresponds to the actual version and evidence on screen.

## 9. Preserve a run record and known limitations

For every new variant record the date/time, VM software revisions, EIDs, TCPCL ports, contact schedule, actual NSTART mode, CoAP methods/resource paths, request MIDs/Tokens, response matches, Wireshark frame numbers and `.pcapng` filename. Distinguish **submitted to local µD3TN** from **delivered to Earth**, and distinguish an **Earth response sent** from a **response received and Token-matched at Rover**. Record failures or missing responses as well as successes.

The modified aiocoap code uses experimental **Payload-length option number `65000`**, not a final standardized assignment; its CoAP Critical/Unsafe bit semantics require review. The current functionality does **not** prove full Draft-05 interoperability, security, cross-application congestion control or deployment-wide reliability. Keep secrets, credentials and private VM runtime data out of the repository.


