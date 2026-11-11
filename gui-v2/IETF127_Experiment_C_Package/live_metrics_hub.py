#!/usr/bin/env python3
"""Rover-side live measurements, sourced from AAP2 callbacks and TShark agents.

Only creates its own UDP observation listener and append-only JSONL evidence.
Never changes the running DTN, CoAP, TCPCL, firewall or contact processes.
A metric is emitted only when its source and correlation checks are satisfied.
"""
import collections
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import re
import socket
import threading
import time

NODE_ADDR = {'rover': '192.168.100.3', 'satellite': '192.168.100.2', 'earth': '192.168.100.1'}
APP_SRC = {'safety': 'ipn:974848.1.10', 'science': 'ipn:974848.1.11'}
EARTH_DST = 'ipn:974848.3.64'


def normalized_eid(eid):
    """RFC 9758 allocator 0 EIDs may be printed as ipn:node.service."""
    m = re.fullmatch(r'ipn:(\d+)\.(\d+)(?:\.(\d+))?', str(eid).strip())
    if not m:
        return str(eid).strip()
    if m.group(3) is None:
        return 'ipn:0.%s.%s' % (int(m.group(1)), int(m.group(2)))
    return 'ipn:%s.%s.%s' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def canonical_bundle_id(s):
    m = re.search(r'Source:\s*(ipn:[0-9.]+),?\s*DTN Time:\s*(\d+),?\s*Seq:\s*(\d+)', str(s))
    if m:
        return '%s|%s|%s' % (normalized_eid(m.group(1)), m.group(2), m.group(3))
    return ''


def iso_epoch(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec='microseconds')


class LiveMetricsHub:
    def __init__(self, bridge, output_path, bind_ip='192.168.100.3', port=56786, window_s=5.0):
        self.bridge = bridge
        self.output_path = Path(output_path).expanduser().resolve()
        self.events_path = self.output_path.with_name(self.output_path.stem + "_events.jsonl")
        self._events_write_lock = threading.Lock()
        self.bind_ip = bind_ip
        self.port = port
        self.window_s = max(1.0, float(window_s))
        self.events = queue.Queue(maxsize=20000)
        self.sock = None
        self.thread = None
        self._stop = threading.Event()
        self.last_seen = {}
        self.clock = {}
        self.clock_samples = collections.Counter()
        self.clock_stepped = {}
        self.clock_history = {}
        self.submitted = collections.Counter()
        self.delivered = collections.Counter()
        self.pending_batches = collections.defaultdict(collections.deque)
        self.bundles = {}
        self.by_bundle = {}
        self.earth_frames = []
        self.earth_downlink_bytes = collections.deque(maxlen=100000)
        self.satellite_outbound = collections.deque(maxlen=2000)
        self.last_rate = 0.0
        self.last_app = 'safety'
        self._last_rate_emit = 0.0
        self.missing_agents_warned = False
        self.stats = collections.Counter()

    def start(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.touch(exist_ok=True)
        self.events_path.touch(exist_ok=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.bind_ip, self.port))
        self.sock.settimeout(0.4)
        self.thread = threading.Thread(target=self._run, name='LiveMetricsHub', daemon=True)
        self.thread.start()
        self.bridge.log('METRICS', 'LIVE capture listener on %s:%d; waiting for 3 read-only agents' %
                        (self.bind_ip, self.port))

    def stop(self):
        self._stop.set()
        if self.sock:
            self.sock.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def attach_backend(self, backend):
        original = backend._engine_event
        def observing_engine_event(app, event, data):
            # Preserve the original callback and every existing behavior.
            if event in ('queued', 'submitted', 'response'):
                try:
                    self.events.put_nowait(('backend', dict(app=app, event=event,
                                                              data=dict(data or {}),
                                                              time_epoch=time.time())))
                except queue.Full:
                    self.bridge.log('ERROR', 'LIVE capture: metrics event queue full')
            return original(app, event, data)
        backend._engine_event = observing_engine_event

    def _append(self, item):
        with self.output_path.open('a', encoding='utf8') as f:
            f.write(json.dumps(item, separators=(',', ':'), ensure_ascii=False) + '\n')
            f.flush()

    def _append_event(self, event, app, **details):
        row = dict(event=event, app=app, time_epoch=time.time(),
                   timestamp_utc=iso_epoch(time.time()), **details)
        with self._events_write_lock:
            with self.events_path.open('a', encoding='utf8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'), default=str) + '\n')

    def record_gui_response(self, app, ev):
        """Store Rover's actual application RTT, not a TCP packet approximation."""
        self._append_event('response', app, code=str(ev.get('code', '')),
                           token=str(ev.get('token', '')), matched=bool(ev.get('matched')),
                           rtt_ms=ev.get('rtt_ms'))

    def _emit(self, app, *, reason, **details):
        # Rover's existing MetricsFeed rejects unsupported values as N/A.
        now = time.time()
        item = dict(app=app, source='Live TShark TCPCL/BPv7 + Rover AAP2 callbacks',
                    evidence_reason=reason, time_epoch=now,
                    timestamp_utc=iso_epoch(now), **details)
        self._append(item)
        self.stats['emitted'] += 1

    def _run(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(64000)
                if len(data) > 10000:
                    continue
                item = json.loads(data.decode('utf8'))
                if not isinstance(item, dict):
                    continue
                node = item.get('node')
                if node not in NODE_ADDR:
                    continue
                # Reject off-testbed origin. Rover local agent may send to loopback.
                expected = NODE_ADDR[node]
                if addr[0] != expected and not (node == 'rover' and addr[0] == '127.0.0.1'):
                    continue
                self.events.put_nowait(('packet', item))
            except socket.timeout:
                pass
            except (OSError, ValueError, UnicodeDecodeError, queue.Full):
                if self._stop.is_set():
                    break
            for _ in range(200):
                try:
                    typ, item = self.events.get_nowait()
                except queue.Empty:
                    break
                try:
                    if typ == 'backend':
                        self._backend(item)
                    else:
                        self._packet(item)
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    self.bridge.log('ERROR', 'LIVE measurement record rejected: %s' % exc)
            if time.monotonic() - self._last_rate_emit >= 1.0:
                self._refresh_rate()
                self._last_rate_emit = time.monotonic()

    def _backend(self, item):
        app, event, data, timestamp = item['app'], item['event'], item['data'], item['time_epoch']
        if app not in APP_SRC:
            return
        if event == 'queued':
            self._append_event('queued', app, token=str(data.get('token', '')),
                               method=str(data.get('method', '')),
                               mid=data.get('mid'), uri=data.get('uri'))
            return
        if event == 'submitted':
            tokens = [str(x) for x in data.get('tokens', []) if x is not None]
            # A single BPv7 bundle can contain multiple CoAP Singles.
            if not tokens:
                return
            raw_kind = str(data.get('bundle_kind') or '').lower().strip()
            kind = ('Aggregate' if raw_kind == 'aggregate' and len(tokens) >= 2
                    else 'Single' if raw_kind == 'single' and len(tokens) == 1
                    else 'Unverified')
            self._append_event('submitted', app, tokens=tokens,
                               bundle_kind=kind, members=len(tokens),
                               bp_payload_bytes=data.get('bytes'))
            self.submitted[app] += len(tokens)
            batch = dict(app=app, tokens=tokens, bytes=data.get('bytes'),
                         submitted_utc=timestamp, id=None, created_monotonic=time.monotonic())
            self.pending_batches[app].append(batch)
            self.last_app = app
            self.bridge.log('METRICS', '%s AAP2 submitted %d CoAP Single(s); waiting for matching Earth bundle' %
                            (app, len(tokens)))
            self._associate_pending(app)
        elif event == 'response':
            # RTT is displayed by original GUI, not interpreted as one-way delay.
            return

    @staticmethod
    def _app_for_request(src, dst):
        src = normalized_eid(src)
        dst = normalized_eid(dst)
        for app, eid in APP_SRC.items():
            if src == eid and dst == EARTH_DST:
                return app
        return None

    def _get_bundle(self, ident):
        if ident not in self.bundles:
            self.bundles[ident] = dict(id=ident, observations={}, assigned=None,
                                      payload_bytes=None, earth_frames=None,
                                      earth_frame_retrans=False)
        return self.bundles[ident]

    def _packet(self, item):
        node = item['node']
        now = time.monotonic()
        self.last_seen[node] = now
        if item.get('event') == 'status':
            clock = item.get('clock') or {}
            if clock.get('checked'):
                self.clock_samples[node] += 1
                # Monotonic-to-realtime checks detect many clock jumps,
                # but not sufficient to guarantee historical perfect sync.
                self.clock[node] = clock
            if node not in self.last_seen or self.stats['status_' + node] == 0:
                self.bridge.log('METRICS', '%s LIVE capture agent connected' % node.upper())
            self.stats['status_' + node] += 1
            return
        if item.get('event') != 'frame':
            return
        self.stats['frames_' + node] += 1
        src, dst = item.get('ip_src'), item.get('ip_dst')
        try:
            event_time = float(item.get('time_epoch'))
            tcp_bytes = max(0, int(item.get('tcp_len', 0)))
            frame_bytes = max(0, int(item.get('frame_len', 0)))
        except (ValueError, TypeError):
            return
        if node == 'earth' and src == NODE_ADDR['satellite'] and dst == NODE_ADDR['earth'] and tcp_bytes > 0:
            self.earth_downlink_bytes.append((now, tcp_bytes))
            self.earth_frames.append(dict(utc=event_time, tcp=tcp_bytes, frame=frame_bytes,
                                          retrans=bool(item.get('retransmission')),
                                          start=bool(item.get('tcpcl_start')),
                                          tcpcl_len=item.get('tcpcl_length')))
            # Prevent unbounded growth when the bundle decoder cannot run.
            if len(self.earth_frames) > 10000:
                self.earth_frames = self.earth_frames[-5000:]
        if node == 'satellite' and src == NODE_ADDR['satellite'] and dst == NODE_ADDR['earth'] and tcp_bytes > 0:
            self.satellite_outbound.append(dict(utc=event_time,
                                               start=bool(item.get('tcpcl_start')),
                                               has_identity=bool(item.get('bundle_identity'))))
        ident = canonical_bundle_id(item.get('bundle_identity', ''))
        if not ident:
            return
        src_eid = normalized_eid(item.get('bp_src', ''))
        dst_eid = normalized_eid(item.get('bp_dst', ''))
        app = self._app_for_request(src_eid, dst_eid)
        if app is None:
            return  # Response bundles are not counted as Earth request receipts.
        b = self._get_bundle(ident)
        if 'app' in b and b['app'] != app:
            return
        b['app'] = app
        observed_key = '%s:%s:%s' % (node, src, dst)
        if observed_key in b['observations']:
            return  # Deduplicate TCP retransmissions and duplicate decoded frames.
        b['observations'][observed_key] = event_time
        b['payload_bytes'] = item.get('bp_payload_bytes')
        if node == 'earth' and src == NODE_ADDR['satellite'] and dst == NODE_ADDR['earth']:
            b['earth_frames'] = self.earth_frames
            self.earth_frames = []
        if node == 'rover' and src == NODE_ADDR['rover'] and dst == NODE_ADDR['satellite']:
            self.bridge.log('BP', 'ROVER captured request bundle %s -> %s' % (src_eid, dst_eid))
        elif node == 'satellite' and src == NODE_ADDR['satellite'] and dst == NODE_ADDR['earth']:
            self.bridge.log('BP', 'SATELLITE forwarded request bundle %s' % ident)
        elif node == 'earth' and src == NODE_ADDR['satellite'] and dst == NODE_ADDR['earth']:
            self.bridge.log('BP', 'EARTH captured complete request bundle %s' % ident)
        self._associate_pending(app)
        self._reconcile(b)

    def _associate_pending(self, app):
        # Match a Rover-AAP2 submitted bundle to its Rover TCPCL capture;
        # same app, same BP payload length, unique oldest batch first.
        available = sorted((b for b in self.bundles.values()
                            if b.get('app') == app and b['assigned'] is None and
                            any(k.startswith('rover:') for k in b['observations'])),
                           key=lambda b: min(b['observations'].values()))
        batches = self.pending_batches[app]
        while available and batches:
            b, batch = available[0], batches[0]
            size = b.get('payload_bytes')
            if not isinstance(size, int):
                break  # Refuse to guess an association without payload lengths.
            if isinstance(batch['bytes'], int) and size != batch['bytes']:
                break
            batch = batches.popleft()
            available.pop(0)
            b['assigned'] = batch
            batch['id'] = b['id']
            self._reconcile(b)

    def _reconcile(self, b):
        batch = b['assigned']
        if batch is None:
            return
        earth_key = 'earth:%s:%s' % (NODE_ADDR['satellite'], NODE_ADDR['earth'])
        earth_recv = b['observations'].get(earth_key)
        if earth_recv is None:
            return
        app = b['app']
        if not b.get('delivered_counted'):
            b['delivered_counted'] = True
            self.delivered[app] += len(batch['tokens'])
            self._append_event('earth_receipt', app, bundle_id=b['id'],
                               tokens=batch['tokens'], members=len(batch['tokens']),
                               bp_payload_bytes=b.get('payload_bytes'),
                               earth_recv_utc=iso_epoch(earth_recv),
                               matching='decoded_BP7_bundle_identity')
            self.bridge.log('METRICS', '%s: Earth receipt verified for %d CoAP Single(s); %d/%d' %
                            (app, len(batch['tokens']), self.delivered[app], self.submitted[app]))
            if self.delivered[app] > self.submitted[app]:
                self.bridge.log('ERROR', 'Inconsistent receipts; delivery percentage suppressed')
                return
            record = dict(earth_received_count=self.delivered[app],
                          rover_submitted_count=self.submitted[app],
                          bundle_id=b['id'],
                          rover_submit_utc=iso_epoch(batch['submitted_utc']),
                          earth_recv_utc=iso_epoch(earth_recv),
                          clock_checked=False, clock_stepped_during_run=None,
                          clock_uncertainty_ms=None,
                          match_method='Rover AAP2 submit -> Rover BPv7 identity/payload -> Earth same BPv7 identity',
                          request_tokens=batch['tokens'],
                          evidence='Earth TCPCL/BPv7 payload fully decoded, not inferred from Rover response')
            # A read-only packet agent cannot prove there were no clock steps
            # during the exchange. Do not fill a one-way delay without a
            # separately verified clock-monitoring pipeline.
            self._emit(app, reason='Earth received matched bundle', **record)
    
        # Optional complete data-bearing Ethernet overhead, only when complete
        # single transfer bounds are verified (header + no retransmissions).
        frames = b.get('earth_frames') or []
        starts = [i for i, f in enumerate(frames) if f['start']]
        # A completed BPv7 decode plus a complete TCPCL length boundary
        # identifies an isolated single-transfer byte span. A TShark TCP
        # reassembly may place START on the *last* frame; don't require it
        # to be at index zero if a complete length boundary is present.
        tcpl_lengths = set()
        for f in frames:
            try:
                if f.get('tcpcl_len') not in (None, ''):
                    tcpl_lengths.add(int(f['tcpcl_len']))
            except ValueError:
                pass
        total_tcp = sum(f['tcp'] for f in frames)
        length_verified = (len(tcpl_lengths) == 1 and
                           1 <= total_tcp - next(iter(tcpl_lengths)) <= 16)
        associated = (starts == [0] or length_verified)
        if (not b.get('overhead_emitted') and frames and associated and
                not any(f['retrans'] for f in frames)):
            captured = sum(f['frame'] for f in frames)
            payload_bytes = b.get('payload_bytes')
            if isinstance(payload_bytes, int) and captured >= payload_bytes:
                b['overhead_emitted'] = True
                self._emit(app, reason='Earth inbound single-bundle frame association',
                           associated_captured_frame_bytes=captured,
                           bp_payload_bytes=payload_bytes, frame_association_verified=True,
                           bundle_id=b['id'],
                           overhead_basis='Data-bearing Ethernet frames minus BPv7 payload; excludes reverse ACKs')

        # Optional Satellite wait: ONLY if a distinct outgoing TCPCL START marker
        # has been observed after the completed incoming bundle, BEFORE the
        # corresponding complete outgoing bundle. Otherwise remain N/A.
        sat_in_key = 'satellite:%s:%s' % (NODE_ADDR['rover'], NODE_ADDR['satellite'])
        sat_out_key = 'satellite:%s:%s' % (NODE_ADDR['satellite'], NODE_ADDR['earth'])
        sat_in, sat_out = b['observations'].get(sat_in_key), b['observations'].get(sat_out_key)
        if sat_in is not None and sat_out is not None:
            candidates = [f['utc'] for f in self.satellite_outbound
                          if f['start'] and not f['has_identity'] and sat_in <= f['utc'] <= sat_out]
            if not b.get('wait_emitted') and len(candidates) == 1 and candidates[0] >= sat_in:
                b['wait_emitted'] = True
                self._emit(app, reason='Satellite TCPCL first outgoing segment after full incoming bundle',
                           satellite_receive_utc=iso_epoch(sat_in),
                           satellite_forward_utc=iso_epoch(candidates[0]),
                           bundle_id=b['id'],
                           note='Same Satellite clock; TCPCL START marker is not a BP custody acknowledgment')

    def _refresh_rate(self):
        # Fixed rolling observation window, independent of request duration.
        # These are TCP payload bytes on the Satellite->Earth TCPCL link,
        # not CoAP application throughput or full-line Ethernet utilization.
        now = time.monotonic()
        while self.earth_downlink_bytes and self.earth_downlink_bytes[0][0] < now - self.window_s:
            self.earth_downlink_bytes.popleft()
        if 'earth' not in self.last_seen or now - self.last_seen['earth'] > 12:
            return
        rate = (8 * sum(n for _, n in self.earth_downlink_bytes)) / (1000 * self.window_s)
        app = self.last_app if self.last_app in APP_SRC else 'safety'
        self._emit(app, reason='Live Earth inbound TCPCL link measurement',
                   window_seconds=self.window_s,
                   window_received_bytes=sum(n for _, n in self.earth_downlink_bytes),
                   note='TCP payload bytes on Satellite->Earth link / fixed rolling window; not CoAP JSON goodput')
