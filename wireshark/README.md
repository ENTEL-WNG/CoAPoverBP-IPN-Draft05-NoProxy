# Wireshark Lua dissector for experimental CoAP-over-BPv7

The Lua plugin `coapbp05_ipn64_PL65000.lua` dissects the **experiment-specific** five-byte CoAP header / **24-bit MID**, experimental Payload-length option **65000**, and Aggregate members embedded as the BPv7 application payload. It registers for **IPN destination service 64** (Earth requests), **10** (Rover Safety responses), and **11** (Rover Science responses).

On **Earth**:

```bash
mkdir -p "$HOME/.local/lib/wireshark/plugins"
cp wireshark/coapbp05_ipn64_PL65000.lua "$HOME/.local/lib/wireshark/plugins/"
```

Close/restart Wireshark and open the `.pcapng`. Capture interface: **enp0s8**. For TCPCLv3 on Earth, Decode As TCP port **4673 → TCPCL** if needed. Display `bpv7` for all bundles; display **`coapbp05.count == 2`** for two-member Aggregates. Expand `CoAP member #1` and `CoAP member #2` to inspect Type, CoAP Code, 24-bit MID, Token, options, Payload-length and CoAP payload.

In the saved Science capture the Aggregate is frame **14** (556-byte BP payload); responses are frames **31** and **49** (54 bytes each) with matching Tokens. **Responses are not aggregated** in the tested path, so they will not match the `count == 2` filter.

This decoder is a research extension, not the standard Wireshark CoAP-over-UDP dissector. The internal label may still say “IPN service 64” when decoding return bundles for service 10/11; inspect the **actual BPv7 destination EID** instead of trusting that static label. The complete decoder should be tested again if the wire format or Payload-length option number changes.

## AI Assistance Acknowledgement

The custom Wireshark Lua dissector for CoAP-over-BPv7 was developed with assistance from ChatGPT (OpenAI) for code generation, refinement, and debugging.

The dissector was subsequently tested and validated against experimental BPv7 packet captures, including Single and Aggregate CoAP messages. Verification included Message IDs, Tokens, Payload-length options, and request-response correlation.

The dissector is a research prototype and is not an official Wireshark plugin.
