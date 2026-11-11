# Payload-size data provenance

`measurements.csv` contains **historical observations with allocator 0** (`ipn:0.1.11` → `ipn:0.3.64`, TCPCLv3 4671–4673). **Do not treat its 40–42 B savings or percentages as measurements for allocator 974848.** The arithmetic is reproducible with `python3 data/verify_calculations.py`, but this script does not parse PCAP files.

`current_allocator974848_observations.csv` records the **limited facts independently supported** by the newer Rover/Earth application logs and Wireshark 4.6.9 screenshots (one Single Safety GET and a two-member Science Aggregate). It is **not** a matched two-Singles-versus-one-Aggregate payload-efficiency benchmark. Empty values indicate that the corresponding measurement was not available and must not be invented.

To recompute the current allocator-974848 efficiency curve, replay matching fixed 50/100/227/500/1000-byte Science POST payloads under identical runtime configuration; capture and save both Singles plus Aggregate for each size; measure the *full reassembled TCPCLv3 data* in the requests, not the packet-list frame length.
