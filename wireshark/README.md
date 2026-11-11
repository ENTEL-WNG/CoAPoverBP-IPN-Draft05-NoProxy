# Wireshark 4.6.9 — three-component IPN and CoAP-over-BPv7 analysis

This folder supports the IETF Hackathon experimental, direct (no-proxy) CoAP-over-BPv7 implementation based on draft-ietf-core-coap-bp-05 and RFC 9758. It contains two complementary tools:

| File | Purpose |
|---|---|
| `coapbp05_ipn64_PL65000.lua` | **Existing repository Lua plugin**: decodes experimental CoAP-over-BPv7 payloads (Single and Aggregate) addressed to IPN services 64, 10 and 11, including 24-bit MIDs, Tokens, and experimental Payload-length option 65000. |
| `wireshark-ipn-live.sh` | **Live capture helper**: captures from the Earth VM's host interface `enp0s8` using `tcpdump`, and streams packets via a named pipe to Wireshark 4.6.9 Flatpak. It does not change µD3TN, AAP2, or CoAP processes. |

**Important:** RFC 9758 three-element IPN EID parsing (`IPN Element Count`, `IPN Allocator`, `IPN Node Number`, `IPN Service Number`) is supplied **natively by Wireshark 4.6.9's BPv7 dissector**, not by either project script. The Lua plugin provides the embedded CoAP decode; the shell script provides live capture when Wireshark is installed through Flatpak.

## Tested three-VM configuration

| Node | Internal interface IP | EID | TCPCLv3 port |
|---|---|---|---|
| Rover | 192.168.100.3 | `ipn:974848.1.0` | 4771 |
| Satellite | 192.168.100.2 | `ipn:974848.2.0` | 4772 |
| Earth | 192.168.100.1 | `ipn:974848.3.0` | 4773 |

Application EIDs: Rover Safety `ipn:974848.1.10`, Rover Science `ipn:974848.1.11`, Earth CoAP `ipn:974848.3.64`. Older repository examples use allocator `0` and ports `4671–4673`; **do not mix configurations**.

## Step 1 — Install the Lua plugin on Earth

With Wireshark 4.6.9 open, go to **Help → About Wireshark → Folders → Personal Lua Plugins** and open the directory shown by *that* installation (the Flatpak location may differ from native Ubuntu Wireshark). Copy `coapbp05_ipn64_PL65000.lua` there and restart Wireshark. The file already exists in this repository and should **not be replaced** merely to display the three-element IPN fields.

If the plugin is loaded, the display filter `coapbp05.count == 2` will be accepted for two-member Aggregates. If not, check plugin path and Lua startup errors.

## Step 2 — Live capture in Wireshark Flatpak on Earth

The Flatpak package does not directly expose native capture interfaces. Install the Wireshark Flatpak and host `tcpdump` before using the helper. From the repository root, run:

```bash
bash wireshark/wireshark-ipn-live.sh enp0s8
```

The default capture filter `ip or ip6` includes TCPCL, ICMP and NTP. To capture only Earth TCPCLv3 traffic in the verified allocator-974848 setup:

```bash
CAPTURE_FILTER='tcp port 4773' bash wireshark/wireshark-ipn-live.sh enp0s8
```

The script asks for `sudo` permission for the host capture and opens a live FIFO in Wireshark 4.6.9. Keep the launcher terminal running. The capture source in Wireshark is a `*.fifo`, **not** an interface named `enp0s8`, although the actual packets come from that interface. No µD3TN or GUI process is stopped or restarted. To check basic reception, use the default broad filter and `ping -c 5 192.168.100.2` from Earth.

For native Wireshark with capture permissions, select `enp0s8` directly instead; the FIFO helper is only needed for the Flatpak workaround.

## Step 3 — Decode and verify the BPv7 bundles

Use these **display filters** in Wireshark (not capture filters):

```text
bpv7
tcp.port == 4773
bpv7.eid.ipn_count == 3
bpv7.eid.ipn_alloc == 974848
coapbp05.count == 1
coapbp05.count == 2
```

If TCPCLv3 appears as TCP only, inspect **Analyze → Decode As** for the traffic's actual port. If reassembly is incomplete, ensure the TCPCL handshake is included where feasible. Save the evidence as `.pcapng` and retain the experiment's matching Rover/Earth application logs.

For the verified Science Aggregate captured on Earth: one BPv7 request bundle carries **two NON POST** members in a **212-byte BP payload**, each with a **50-byte Payload-length**; requested/observed BP lifetime **90,000 ms**. Member MIDs were `2543436` and `2543437` with different Tokens. Earth returned separate `2.01 Created` responses. In Wireshark the source and destination EIDs showed **IPN Element Count: 3** with allocator `974848`.

These observed values are from a specific lab run, not constants of the draft. The use of Payload-length option **65000** and NSTART=2 is experimental; full Draft-05 interoperability or congestion safety has not been demonstrated.

## AI assistance acknowledgement

AI tools assisted with authoring and editing the experimental Lua dissector, the live-capture helper and these participant instructions. The working project implementation and observed experimental results were reviewed against captured traffic; these helpers are research tools, not official Wireshark extensions.

## References

- [CoAP over BPv7 draft-05](https://datatracker.ietf.org/doc/draft-ietf-core-coap-bp-05/)
- [RFC 9758 — IPN EID scheme](https://www.rfc-editor.org/rfc/rfc9758)
- [Wireshark BPv7 fields](https://www.wireshark.org/docs/dfref/b/bpv7.html)
- [Wireshark capture from pipes](https://wiki.wireshark.org/CaptureSetup/Pipes)
