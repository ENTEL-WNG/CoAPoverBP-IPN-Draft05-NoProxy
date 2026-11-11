# Narration transcript — Wireshark 4.6.9 + Lua dissector tutorial

**IETF 127 Hackathon · CoRE · DTN** — companion to `IETF127_Wireshark_Lua_Tutorial_Narrated.mp4`.

Onsite Champion: Prof. Anna Calveras · Remote Champion: Mahitab S. Elattar · Wireless Networks Group, UPC

Timestamps mark where each slide starts in the video.

## 01 · Welcome  `00:00`

Welcome to this IETF 127 Hackathon tutorial. In the next few minutes, you will learn how to use Wireshark 4.6.9 and our Lua dissector to see CoAP messages travelling inside Bundle Protocol version 7 bundles. This work is championed onsite by Professor Anna Calveras, and remotely by Mahitab S. Elattar, of the Wireless Networks Group at UPC.

## 02 · What this tutorial enables  `00:28`

First, one important idea. The experiment itself is implemented by modified aiocoap applications on the Rover and on Earth, talking through AAP2 to patched µD3TN bundle nodes. Wireshark only observes. tcpdump or dumpcap captures the packets, and our Lua dissector adds CoAP field-level decoding. It is a dissector: not a transport, not a proxy, and not a router. The question we answer together is simple: can one BPv7 bundle carry two non-confirmable POST requests, and still deliver two correctly matched responses? To find out, we inspect the real frames, endpoint IDs, lifetime, message IDs and tokens.

## 03 · The three-node testbed  `01:16`

Here is the testbed. The Rover, at 192.168.100.3, runs the Safety client on service 10, and the Science client on service 11. The Satellite, at 192.168.100.2, is only a BPv7 relay. It forwards bundles, and it has no CoAP proxy. Earth, at 192.168.100.1, runs the CoAP server on service 64. We capture on Earth, on interface enp0s8, where the Satellite delivers bundles over TCPCL version 3, on port 4773.

## 04 · Match the ports and EIDs of your run  `01:59`

Before you filter anything, check which configuration your lab is running. The recorded experiment uses allocator 974848, with TCPCL ports 4771, 4772 and 4773. Older repository documentation describes a baseline with allocator 0, and ports 4671 to 4673. So always check the running µD3TN node ID and CLA settings, and use the values from your own lab. Please do not mix the two.

## 05 · Why Wireshark 4.6.9?  `02:37`

Why Wireshark 4.6.9? Because its native BPv7 decoder shows the RFC 9758 endpoint fields directly. Take Earth's CoAP endpoint, ipn:974848.3.64. Scheme code 2 tells you that this endpoint uses the IPN scheme. An IPN element count of 3 tells you the address is encoded as three separate parts: allocator, node, and service. Here, the allocator is 974848, the node is 3, and the service is 64, Earth's CoAP application. Remember: scheme code and element count are two different fields.

## 06 · Use the Lua file already in the repository  `03:22`

You do not need to write a new dissector. Clone the project repository, ENTEL-WNG/CoAPoverBP-IPN-Draft05-NoProxy, or use your existing checkout. The experimental Lua file is in the wireshark folder. It decodes the BPv7 payload for IPN services 10, 11 and 64.

## 07 · Install the plugin in your personal Lua folder  `03:47`

Next, find where your Wireshark looks for Lua plugins. Open Help, About Wireshark, then Folders, and look for Personal Lua Plugins. Create that folder if it is missing, and copy the Lua file into it. Always use the exact folder that your running Wireshark shows you. On a native Linux install, this is usually ~/.local/lib/wireshark/plugins. The Flatpak version may use a different path. Then restart Wireshark.

## 08 · Check that the Lua dissector loaded  `04:19`

To check that the dissector loaded, open a bundle capture or start live traffic, and try these display filters. They go in Wireshark's filter bar, not in a terminal. bpv7 shows all bundles. coapbp05.count == 1 shows Single bundles, and coapbp05.count == 2 shows a two-member Aggregate. bpv7.eid.ipn_count == 3 shows three-element IPN addresses. In the packet details, you should see DTN Bundle Protocol Version 7, then CoAP over BPv7, then each CoAP member. If the count filter is not recognized, check the plugin folder, and look for Lua errors at startup.

## 09 · Two supported capture workflows  `05:08`

There are two supported ways to capture. With native Wireshark, simply select enp0s8 in the interface list, and start the capture before the new TCPCL traffic. Optionally, use a capture filter for TCP port 4773. With the Wireshark 4.6.9 Flatpak, the sandbox cannot capture enp0s8 directly. Instead, host tcpdump sends the packets through a named pipe into Wireshark. These are still genuine, live packets. The named-pipe workaround is the one used in the verified Earth demonstration.

## 10 · How the Flatpak capture works  `05:49`

Here is how that pipe works. The packets stay on the real interface, enp0s8, on Earth. Host tcpdump reads the live frames, and streams them, unbuffered, through a named pipe. The sandboxed Wireshark reads the pipe, and decodes TCPCL version 3, BPv7, and CoAP with the Lua plugin. On Earth, run the helper script from the scripts folder, with the interface name. Keep its terminal open while you capture; it does not restart µD3TN or any application. To capture only the Earth TCPCL port, set the capture filter to tcp port 4773.

## 11 · Find your TCPCLv3 conversation  `06:33`

Now, find your TCPCL conversation. At first, packets may appear as plain TCP. Use the display filter tcp.port == 4773 for the current run, or 4673 for the older baseline, together with bpv7. If the packets still remain TCP, use Analyze, Decode As, and select TCPCL version 3 for port 4773. And start the capture before the TCPCL handshake when you can, because TCP reassembly matters. One more tip: a single Ethernet frame's length is not the full bundle or payload length. Always read the reassembled values.

## 12 · One NON GET inside one BPv7 bundle (frame 14)  `07:19`

Let's look at real results. Frame 14 is the Single request, captured on Earth. It travels from the Rover Safety service, ipn:974848.1.10, to Earth's CoAP service, ipn:974848.3.64, over TCPCL version 3. Inside is exactly one non-confirmable GET, with its 24-bit message ID and token, in a 59-byte BP payload. Because it is a Single message, there is no Payload-length option.

## 13 · Earth returns a separate Single response (frame 31)  `07:56`

Earth replies in a separate bundle, frame 31, from ipn:974848.3.64 back to ipn:974848.1.10. It is a non-confirmable 2.05 Content response, in a 103-byte payload. And it carries the request's token, 684d4727, so the Rover can match it.

## 14 · Aggregate test: two Science POSTs, one bundle  `08:24`

Now, the Aggregate test. In this controlled experiment, NSTART is set to two, the buffer limit is two messages, and the aggregation timer is ten seconds. The Science client queues two non-confirmable POSTs. Each has its own 24-bit message ID and token, and each carries 50 bytes of application payload. Both share the same source, ipn:974848.1.11, and the same destination, ipn:974848.3.64.

## 15 · Frame 76: one bundle, two POSTs  `09:00`

Frame 76 shows the result. One BPv7 bundle travels from ipn:974848.1.11 to ipn:974848.3.64. Its 212-byte application payload contains two CoAP POST messages: one bundle, not two separate request bundles.

## 16 · Lua exposes each Aggregate member  `09:26`

The Lua dissector expands each member independently. Here is member one: a non-confirmable POST. You can read its 24-bit message ID, 2543436, and its token, 2f8ecb82. Member two follows, with the next message ID and its own token. Each member also shows its URI options and the experimental Payload-length option: 50 bytes.

## 17 · Three-element IPN, confirmed for both EIDs  `09:55`

Wireshark 4.6.9 confirms the addressing for both endpoints. Scheme code 2 means IPN. The IPN element count is 3. The allocator is 974848. The source is node 1, service 11, and the destination is node 3, service 64.

## 18 · Verify bundle lifetime and integrity  `10:16`

Next, verify the bundle's lifetime and integrity in the BPv7 primary block. The version is 7. The lifetime is 90,000 milliseconds, that is, 90 seconds. The CRC type is CRC-16, and the CRC status is Good. Remember to read these values from the primary block, not from the Ethernet frame length.

## 19 · Every request got its matching reply  `10:41`

Finally, the application view. Rover Mission Control reports four of four matching Safety replies, and three of three matching Science replies. The two Aggregate POST members received separate 2.01 Created responses, each with its matching token.

## 20 · What to claim — and what not to claim  `10:59`

When you present your results, be precise. Verified: Single and Aggregate framing, three-element endpoint IDs, and token-matched responses. Experimental: Payload-length option number 65000 is not a final assigned number, so inspect its option properties before making standards claims. Congestion: NSTART of two was used only in a controlled test, so congestion safety still needs deployment-specific analysis. And scope: the Lua plugin decodes traffic. It does not implement CoAP, routing, or a proxy. This is a working prototype, not proof of full draft-five conformance or interoperability.

## 21 · Share a reproducible run in six steps  `11:44`

To share a reproducible run, follow these six steps. One: install the matching Lua plugin, in the folder Wireshark shows you. Two: start the capture before the test, using native enp0s8 or the Flatpak pipe launcher. Three: confirm the decoding: TCPCL version 3, then BPv7, then CoAP over BPv7. Four: record the IPN fields: element count, allocator, node and service. Five: record the transaction details: message IDs, tokens, payload sizes, lifetime and replies. And six: save the pcapng file and the logs, without secrets, credentials, or private local files.

## 22 · Thank you  `12:30`

Everything you need is in the repository: the experimental Lua dissector, the code, captures, and setup documentation. Thank you for following this tutorial. Onsite Champion: Professor Anna Calveras. Remote Champion: Mahitab S. Elattar. Enjoy the Hackathon!
