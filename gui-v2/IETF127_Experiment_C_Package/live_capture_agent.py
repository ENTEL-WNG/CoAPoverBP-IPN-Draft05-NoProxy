#!/usr/bin/env python3
"""Read-only, live TCPCLv3/BPv7 observation agent for an IETF127 three-VM lab.

On Rover, Satellite, or Earth: capture via TShark (-l), send observations to
Rover's Mission Control using *out-of-band* UDP (port 56786). This UDP traffic
is NOT part of the DTN measurement; only TCPCL ports are captured. No daemon
configuration, routing, or AAP2 registrations are modified.

Run with Python 3.8+ (only the standard library is imported).
"""
import argparse
import json
import os
import re
import shutil
import signal
import socket
import threading
import subprocess
import sys
import time

IP = {'rover': '192.168.100.3', 'satellite': '192.168.100.2', 'earth': '192.168.100.1'}
FIELDS = [
    'frame.time_epoch', 'ip.src', 'ip.dst', 'tcp.len', 'frame.len',
    'bpv7.bundle.identity', 'bpv7.primary.src_uri', 'bpv7.primary.dst_uri',
    '_ws.col.Info', 'tcp.analysis.retransmission', 'tcpcl.data.proc.start',
    'tcpcl.data.length',
]


def has_required_fields():
    p = subprocess.run(['tshark', '-G', 'fields'], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, check=False)
    if p.returncode:
        raise RuntimeError('tshark -G fields failed: ' + p.stderr[:250])
    defined = {line.split('\t')[2] for line in p.stdout.splitlines()
               if line.startswith('F\t') and len(line.split('\t')) >= 3}
    # _ws.col.Info is a generated column, not a registered filter field.
    missing = [n for n in FIELDS if n != '_ws.col.Info' and n not in defined]
    if missing:
        raise RuntimeError('Unsupported TShark display fields: ' + ', '.join(missing)
                           + '. Send the output of tshark --version and tshark -G fields.')


def info_identity(info):
    """Fallback when the bundle identity field is unavailable/empty."""
    m = re.search(r'Src:\s*(ipn:[0-9.]+).*?Dst:\s*(ipn:[0-9.]+).*?Time:\s*(\d+).*?Seq:\s*(\d+)', info)
    if m:
        return 'Source: %s, DTN Time: %s, Seq: %s' % (m.group(1), m.group(3), m.group(4))
    return ''


def parse_row(line):
    cells = line.rstrip('\r\n').split('\t')
    if len(cells) != len(FIELDS):
        return None
    r = dict(zip(FIELDS, cells))
    try:
        t = float(r['frame.time_epoch'])
        tcp_len = int(r['tcp.len'] or '0')
        frame_len = int(r['frame.len'] or '0')
    except (ValueError, OverflowError):
        return None
    if not r['ip.src'] or not r['ip.dst'] or tcp_len < 0:
        return None
    info = r['_ws.col.Info']
    identity = r['bpv7.bundle.identity'] or info_identity(info)
    payload_size = None
    m = re.search(r'Payload-Size:\s*(\d+)', info, re.I)
    if m:
        payload_size = int(m.group(1))
    return {
        'event': 'frame', 'time_epoch': t, 'ip_src': r['ip.src'],
        'ip_dst': r['ip.dst'], 'tcp_len': tcp_len, 'frame_len': frame_len,
        'bundle_identity': identity, 'bp_src': r['bpv7.primary.src_uri'],
        'bp_dst': r['bpv7.primary.dst_uri'], 'bp_payload_bytes': payload_size,
        'retransmission': bool(r['tcp.analysis.retransmission']),
        'tcpcl_start': r['tcpcl.data.proc.start'] in ('1', 'True', 'true'),
        'tcpcl_length': r['tcpcl.data.length'],
    }


def get_clock_status():
    """Conservative NTP bound, for informational use; not proof of clock history."""
    try:
        p = subprocess.run(['chronyc', 'tracking'], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, timeout=3)
        if p.returncode:
            return {'checked': False}
        values = {}
        for line in p.stdout.splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                values[k.strip()] = v.strip()
        def number(k):
            x = re.search(r'[-+]?\d+(?:\.\d+)?', values.get(k, ''))
            return float(x.group()) if x else None
        offset, delay, dispersion = number('System time'), number('Root delay'), number('Root dispersion')
        leap = values.get('Leap status', '')
        checked = all(x is not None for x in (offset, delay, dispersion)) and leap == 'Normal'
        bound_ms = 1000 * (offset + delay / 2 + dispersion) if checked else None
        return {'checked': checked, 'uncertainty_bound_ms': bound_ms,
                'leap_status': leap, 'sample_time_epoch': time.time()}
    except (OSError, subprocess.TimeoutExpired):
        return {'checked': False}


def command_for_capture(iface):
    cmd = [
        'tshark', '-l', '-n', '-i', iface, '-f',
        'tcp and (port 4671 or port 4672 or port 4673)',
        '-d', 'tcp.port==4671,tcpcl',
        '-d', 'tcp.port==4672,tcpcl',
        '-d', 'tcp.port==4673,tcpcl',
        '-T', 'fields', '-E', 'separator=/t', '-E', 'quote=n', '-E', 'occurrence=f',
    ]
    for field in FIELDS:
        cmd.extend(['-e', field])
    return cmd


def main():
    p = argparse.ArgumentParser(description='Read-only live BPv7 capture -> Rover GUI UDP telemetry')
    p.add_argument('--node', required=True, choices=IP)
    p.add_argument('--collector', default='192.168.100.3', help='Rover intnet IP')
    p.add_argument('--port', type=int, default=56786)
    p.add_argument('--interface', default='enp0s8')
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    if not shutil.which('tshark'):
        p.error('tshark is not installed')
    has_required_fields()
    cmd = command_for_capture(args.interface)
    if args.check_only:
        print('Required TShark fields: OK')
        print('Capture command: ' + ' '.join(cmd))
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    dest = (args.collector, args.port)
    def send(d):
        d['node'] = args.node
        d['agent_version'] = 1
        try:
            sock.sendto(json.dumps(d, separators=(',', ':')).encode('utf8'), dest)
        except (BlockingIOError, OSError):
            pass  # Non-blocking: measurement reporting must never stall TCPCL.
    print('Starting read-only %s capture on %s -> %s:%s' % (args.node, args.interface, *dest), flush=True)
    send({'event': 'status', 'clock': get_clock_status(), 'time_epoch': time.time()})
    heartbeat_stop = threading.Event()
    def heartbeat():
        while not heartbeat_stop.wait(8.0):
            send({'event': 'status', 'clock': get_clock_status(),
                  'time_epoch': time.time()})
    threading.Thread(target=heartbeat, daemon=True).start()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1)
    def stop(_sig, _frame):
        if proc.poll() is None:
            proc.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    count = 0
    try:
        # TShark's -l produces one row per frame as packets arrive.
        for line in proc.stdout:
            row = parse_row(line)
            if row is None:
                continue
            send(row)
            count += 1
            if count % 50 == 0:
                send({'event': 'status', 'clock': get_clock_status(),
                      'time_epoch': time.time(), 'frames_seen': count})
    except KeyboardInterrupt:
        pass
    finally:
        heartbeat_stop.set()
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        sock.close()
        print('Stopped; observed %d TCP frames' % count, flush=True)
    if count == 0 and proc.returncode not in (0, -15, -2):
        raise RuntimeError('TShark exited without frames; check capture permissions and interface')


if __name__ == '__main__':
    main()
