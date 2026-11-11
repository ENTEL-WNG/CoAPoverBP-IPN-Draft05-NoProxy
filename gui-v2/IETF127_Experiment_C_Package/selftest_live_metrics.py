#!/usr/bin/env python3
"""Offline correlation test. Does not open any socket, send bundles, or start TShark."""
import json
from pathlib import Path
import tempfile
import time
from live_metrics_hub import LiveMetricsHub, normalized_eid, canonical_bundle_id
from live_capture_agent import FIELDS, parse_row

class Bridge:
    def __init__(self):
        self.lines = []
    def log(self, level, msg):
        self.lines.append((level, msg))

assert normalized_eid('ipn:1.10') == 'ipn:0.1.10'
assert canonical_bundle_id('Source: ipn:1.10, DTN Time: 847388061773, Seq: 1') == 'ipn:0.1.10|847388061773|1'

with tempfile.TemporaryDirectory() as d:
    out = Path(d) / 'live.jsonl'
    hub = LiveMetricsHub(Bridge(), out)
    hub._backend({'app':'safety', 'event':'submitted',
                  'data':{'tokens':['abc12345'], 'bytes':54, 'bundle_kind':'Single'},
                  'time_epoch':1794072861.773})
    identity = 'Source: ipn:1.10, DTN Time: 847388061773, Seq: 1'
    def frame(node, src, dst, t, n, payload=None, start=False):
        return dict(node=node, event='frame', time_epoch=t, ip_src=src, ip_dst=dst,
                    tcp_len=n, frame_len=n+66,
                    bp_src='ipn:1.10', bp_dst='ipn:3.64',
                    bp_payload_bytes=payload,
                    bundle_identity=identity if payload else '',
                    retransmission=False, tcpcl_start=start)
    hub._packet(frame('rover','192.168.100.3','192.168.100.2',1794072861.817,1,54))
    hub._packet(frame('satellite','192.168.100.3','192.168.100.2',1794072861.8178,1,54))
    hub._packet(frame('satellite','192.168.100.2','192.168.100.1',1794072861.8193,2))
    hub._packet(frame('satellite','192.168.100.2','192.168.100.1',1794072861.8214,95,54))
    hub._packet(frame('earth','192.168.100.2','192.168.100.1',1794072861.8207,2))
    hub._packet(frame('earth','192.168.100.2','192.168.100.1',1794072861.8210,5))
    hub._packet(frame('earth','192.168.100.2','192.168.100.1',1794072861.8233,95,54))
    hub._refresh_rate()
    records=[json.loads(s) for s in out.read_text().splitlines()]
    assert hub.submitted['safety'] == 1, hub.submitted
    assert hub.delivered['safety'] == 1, (hub.delivered, hub.bridge.lines)
    assert any(x.get('earth_received_count')==1 and x.get('rover_submitted_count')==1 for x in records), records
    assert any(x.get('window_received_bytes')==102 for x in records), records
    assert all('delay_ms' not in x for x in records), 'one-way delay must not be fabricated'
    print('PASS: BPv7 identities match despite two-component display')
    print('PASS: live Earth receipt / Rover submitted ratio = 1/1')
    print('PASS: link throughput uses 102 captured TCP data bytes over a fixed 5-s window')
    print('PASS: no unverified one-way delay')

cells=['1794072861.823344000','192.168.100.2','192.168.100.1','95','161',identity,
       'ipn:1.10','ipn:3.64','Payload-Size: 54','','','95']
assert len(cells)==len(FIELDS)
r=parse_row('\t'.join(cells)+'\n')
assert r['bp_payload_bytes']==54 and r['bundle_identity']==identity
print('PASS: TShark field row parser')
