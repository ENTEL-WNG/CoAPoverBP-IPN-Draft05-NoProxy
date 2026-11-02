# IETF 127 demonstration — CoAP-over-BPv7 Draft-05, IPN no proxy

**Audience:** project supervisors / IETF hackathon participants. **Goal:** visibly show that two distinct CoAP requests travel inside **one BPv7 request bundle**, with independent MIDs and Tokens, through Rover→Satellite→Earth, and that Earth replies to each request. **No proxy** is used.

> This guide reproduces the known laboratory procedure. A new VM installation still requires the patched µD3TN checkout and compatible Python environments described in [installation.md](installation.md). **Avoid modifying the live working files in order to run a demonstration.**

## Preparation checklist

- Three powered-on VirtualBox VMs, with `enp0s8` IPs `192.168.100.3` (Rover), `.2` (Satellite) and `.1` (Earth); verify ping.
- Correct **patched** `ud3tn` binary on all three VMs and working AAP2 sockets.
- Earth CoAP application `ipn:0.3.64`; Rover Safety `ipn:0.1.10` and Science `ipn:0.1.11`.
- Wireshark on **Earth** (capture interface `enp0s8`; TCPCLv3 over TCP port **4673**); experimental Lua plugin installed if detailed CoAP fields are needed.
- No live previous run using the same sockets/ports; **reuse existing processes or stop them deliberately before starting another instance**.

## 1. Start or confirm µD3TN on the three nodes

Each block runs on the **named VM**, in its own terminal, and stays running. All commands are from the successful lab configuration. The helper `scripts/start_ud3tn.sh` prints a clear error if the patched binary is missing:

**Rover VM:**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh rover
```

**Satellite VM:**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh satellite
```

**Earth VM:**

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/start_ud3tn.sh earth
```

For reference, the tested executable used `--node-id ipn:0.X.0 --aap-socket /tmp/...aap1.sock --aap2-socket /tmp/...aap2.sock --cla 'tcpclv3:*,PORT' --bp-version 7 --log-level 4` with **ports 4671, 4672, 4673 respectively**. `scripts/start_ud3tn.sh` supplies these values.

## 2. Install/reinstall the four one-hour forwarding contacts

Use a **new terminal** on each VM; keep the daemons running. These script commands are the tested contact configuration, with a 3600-second duration and a 100000-byte volume parameter. Run them just before the experiment because the contacts expire.

**Satellite** (both forwarding directions):

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/satellite_contacts.sh
```

**Earth** (return through Satellite):

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_contacts.sh
```

**Rover** (reach Earth through Satellite):

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/rover_contacts.sh
```

Check the respective µD3TN terminal for routing ADD/FIB entries and a successful TCPCL handshake. **A route command exiting successfully alone does not prove packets were forwarded.**

## 3. Run the CoAP applications

**Earth**, in another terminal:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/earth_server.sh
```

**Rover**, in a graphical Ubuntu desktop terminal:

```bash
cd ~/CoAPoverBP-IPN-Draft05-NoProxy
./scripts/rover_gui.sh
```

GUI status should report **Safety: Registered | Science: Registered**. It may need the original rover-background image asset from the lab; see [installation.md](installation.md). For this controlled experiment the engine parameters were **NSTART=2 per application**, **BUFFER_LIMIT=2**, **MAX_AGGR_DELAY_SECONDS=10**. This is **not a congestion-safety result**.

## 4. Start packet capture on Earth

1. Start Wireshark → `enp0s8`. Optional capture filter: `tcp port 4673`. Choose the **Earth TCPCL port 4673**, not the other nodes' ports.
2. Set **Decode As** for TCP port **4673 → TCPCLv3** if needed.
3. Use display filter `bpv7` to see request and response bundles.
4. With the Lua plugin installed, use **`coapbp05.count == 2`** to show the Aggregate requests and expand **CoAP member #1 / #2**. Responses are individual Single messages, so inspect them under `bpv7`.
5. Save the capture in `.pcapng` format with the interface, date, test and NSTART value in the filename.

Install the already-packaged dissector on Earth, if necessary:

```bash
mkdir -p "$HOME/.local/lib/wireshark/plugins"
cp ~/CoAPoverBP-IPN-Draft05-NoProxy/wireshark/coapbp05_ipn64_PL65000.lua \
   "$HOME/.local/lib/wireshark/plugins/"
# Close and relaunch Wireshark to load the plugin.
```

## 5. Run three visible checks

| Demo | Rover action | On Earth / Rover, expected observable result |
| --- | --- | --- |
| Single baseline | Click **ROVER SAFETY GET** once and allow 10 s for timer flush | One Single CoAP GET in **54-byte BPv7 payload**; response code `2.05 Content`; Payload-length option absent |
| Safety Aggregate | Click **ROVER SAFETY GET** **twice within 10 s**, after the previous request has finished | **One 116-byte BPv7 request payload** containing 2 NON GET members (Payload-length 3 each); 2 Single 2.05 responses; distinct request MIDs and Tokens |
| Science Aggregate | Click **ROVER SCIENCE POST** **twice within 10 s** | **One 556-byte BPv7 request payload** containing 2 NON POST members (Payload-length 227 each); 2 Single 2.01 responses; distinct MIDs and Tokens |

If both requests do not land inside the same Aggregate, verify that the GUI **does not immediately call `flush_coap_buffer()`** on every click and is loading the experimental `NodeA_Mission_Draft05_Aggregation.py`. Recheck NSTART and the 10-second timer in the **running** process. Do not manually alter a working live implementation during an IETF demo.

## 6. Packet walkthrough: saved Science proof

The committed capture `evidence/science/Earth_Draft05_IPN_Science_Aggregate_NSTART2.pcapng` was inspected with the Lua plugin:

| Frame | Direction | BPv7 payload | CoAP fields |
| --- | --- | ---: | --- |
| **14** | Rover Science `ipn:1.11` → Earth `ipn:3.64` | **556 B** | 2 NON POST members; MIDs **4858056, 4858057**; Tokens **`9fc152cf`, `5ae01fab`**; URI `/science/observations`; Payload-length **227** each |
| **31** | Earth `ipn:3.64` → Rover Science `ipn:1.11` | **54 B** | Single NON **2.01 Created**, response MID **15**, Token **`9fc152cf`** |
| **49** | Earth `ipn:3.64` → Rover Science `ipn:1.11` | **54 B** | Single NON **2.01 Created**, response MID **16**, Token **`5ae01fab`** |

Wireshark displays `ipn:1.11`/`ipn:3.64` as abbreviations of zero-allocator three-part EIDs. The BPv7 `Payload-Size` values (556 and 54) are **not** Ethernet frame lengths. **Do not use the recorded example MIDs as predictions for new runs**; the client/server counters change over time.

The **earlier console run** with request MIDs **4858053 / 4858054** and matched Rover responses is **not** the same run as the above packet capture. Request/response evidence at Earth's interface is strong packet-level evidence; to state end-to-end delivery to Rover **for a particular captured run**, preserve corresponding Rover terminal logs showing the matching Tokens and `Pending: 0`.

## 7. Suggested 5-minute spoken demonstration

1. **30 s:** Show topology; explain that Satellite forwards BP bundles and does **not** translate CoAP.
2. **45 s:** Show IPN allocator/node/service addressing (`ipn:0.1.11` → `ipn:0.3.64`) and the `.ipn.alt` URI.
3. **60 s:** Show two Science POST clicks and the `SENDING AGGREGATE` Rover log.
4. **90 s:** Open the **556-byte** request in Wireshark; expand two CoAP members and show independent MIDs, Tokens, Payload-length option.
5. **45 s:** Show two return Single response bundles and exact Token matches.
6. **30 s:** State limitations: experimental option 65000, NSTART=2 not congestion-safe by proof, no aggregated responses, fresh clone pending validation.

**One-slide content:** `IPN-only no-proxy architecture | Rover Safety/Science | 24-bit MID + Payload-length | 2→1 bundle aggregation | 556-B Wireshark proof | two matching responses` and a link to the demo recording **when one is available**. Do not invent a video URL.

## 8. Preserve a run record

Create `experiments/<date>-<test>/README.md` noting VM versions, code/patch Git commit, running configuration, precise contact start/end times, request and response MIDs/Tokens, observed `bpv7` frame numbers, and capture filenames. Keep raw credential-bearing logs out of Git. Capture a fresh `.pcapng` for every important variant and correlate it with the two application terminal logs.
