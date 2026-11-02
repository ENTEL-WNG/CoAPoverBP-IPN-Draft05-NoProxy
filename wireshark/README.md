# Wireshark Lua dissector

`coapbp05_ipn64_PL65000.lua` parses this experiment's modified 5-byte CoAP header with 24-bit MID and experimental Payload-length option **65000** inside BPv7 payloads addressed to IPN services 64 (Earth CoAP), 10 (Rover Safety) and 11 (Rover Science).

On the **Earth VM**:

```bash
mkdir -p ~/.local/lib/wireshark/plugins
cp coapbp05_ipn64_PL65000.lua ~/.local/lib/wireshark/plugins/
```

Restart Wireshark, open an actual experimental capture, ensure BPv7/TCPCL is decoded, and filter `coapbp05.count == 2`. For responses use `bpv7` and inspect the CoAP member Token. This Lua decoder reflects an experimental wire format, not standard UDP CoAP dissection. The packaged extension to services 10/11 should be revalidated when installing on another system.
