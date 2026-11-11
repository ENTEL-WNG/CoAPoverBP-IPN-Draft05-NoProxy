#!/usr/bin/env python3
"""Check historical allocator-0 byte-savings observations only.
This is NOT a benchmark for the current allocator 974848 configuration.
The script does not parse pcapng files or verify raw capture authenticity.
"""
from pathlib import Path
import csv
p=Path(__file__).with_name('measurements.csv')
with p.open(newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        size = int(row['payload_bytes'])
        s = int(row['single_tcp_reassembled_bytes_each'])
        a = int(row['aggregate_tcp_bytes'])
        saved = 2*s-a
        pct = 100*saved/(2*s)
        assert int(row['saved_tcp_bytes']) == saved
        assert abs(float(row['saving_percent'])-pct) < .0001
        assert int(row['aggregate_bp_payload_bytes'])-2*int(row['single_bp_payload_bytes_each']) == int(row['payload_length_extra_bytes_total'])
        print(f'{size:4} B: 2 x {s} B - {a} B = {saved} B saved ({pct:.2f}%)')
print('PASS: historical allocator-0 calculations are internally consistent (NOT 974848 measurements)')
