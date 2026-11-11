#!/usr/bin/env python3
"""Fail-closed GUI send gate; supplements, never replaces, CoAP engine NSTART.

RFC7252 outstanding interactions = awaiting a response/ACK, not only bytes in flight.
No automatic timeout-based credit release, because DTN delays can be long.
Applies only to requests initiated by this GUI, not to other AAP2 clients.
"""
from collections import deque
import threading
import time


class CongestionGuard:
    def __init__(self, backend, bridge, max_outstanding=1, min_gap_ms=100):
        if max_outstanding not in (1, 2):
            raise ValueError('Only NSTART 1 baseline / 2 controlled lab experiment supported')
        self.backend = backend
        self.bridge = bridge
        self.limit = max_outstanding
        self.gap_s = max(0.0, float(min_gap_ms)) / 1000
        self._lock = threading.Lock()
        self._reservations = {'safety': deque(), 'science': deque()}
        self._last_send = 0.0
        self._seq = 0

    def attach_backend(self):
        previous = self.backend._engine_event

        def observer(app, event, data):
            # Observe first, then pass exactly the same event to the original
            # backend, preserving its callback, RTT and application behavior.
            self._event(app, event, dict(data or {}))
            return previous(app, event, data)
        self.backend._engine_event = observer

    def _event(self, app, event, data):
        if app not in self._reservations:
            return
        with self._lock:
            q = self._reservations[app]
            if event == 'queued':
                token = str(data.get('token', ''))
                res = next((r for r in q if r['token'] is None), None)
                if res is not None and token:
                    res['token'] = token
            elif event == 'response' and bool(data.get('matched')):
                token = str(data.get('token', ''))
                res = next((r for r in q if r['token'] == token and token), None)
                if res is not None:
                    q.remove(res)
            elif event in ('rejected', 'timeout'):
                token = str(data.get('token', ''))
                res = next((r for r in q if r['token'] == token and token), None)
                if res is not None:
                    q.remove(res)
        if event == 'submitted':
            tokens = data.get('tokens') or []
            count = len(tokens)
            kind = str(data.get('bundle_kind') or '').strip().lower()
            if count > self.limit:
                self.bridge.log('ERROR', '%s: observed %d Singles in one bundle exceeds GUI NSTART cap %d' %
                                (app, count, self.limit))
            if kind == 'aggregate' and count < 2:
                self.bridge.log('ERROR', '%s: engine said Aggregate but submitted fewer than 2 Singles' % app)

    def send(self, app):
        if app not in self._reservations:
            return
        with self._lock:
            # Backend is connected to the working µD3TN engine; no daemon starts.
            if app not in self.backend.ready or app not in self.backend.mods:
                self.bridge.log('INFO', '%s: waiting for AAP2 registration; not sent' % app)
                return
            mod = self.backend.mods[app]
            engine_nstart = getattr(mod, 'NSTART', 1)
            if not isinstance(engine_nstart, int) or engine_nstart < self.limit:
                self.bridge.log('ERROR', '%s: engine NSTART=%s is lower than GUI cap=%s; not sent' %
                                (app, engine_nstart, self.limit))
                return
            outstanding_app = len(self._reservations[app])
            outstanding_all = sum(map(len, self._reservations.values()))
            if outstanding_app >= self.limit or outstanding_all >= self.limit:
                self.bridge.log('INFO', 'CONGESTION GUARD: blocked %s, outstanding=%d/%d app and %d/%d shared; NSTART limit' %
                                (app, outstanding_app, self.limit, outstanding_all, self.limit))
                return
            now = time.monotonic()
            if now - self._last_send < self.gap_s:
                self.bridge.log('INFO', 'CONGESTION GUARD: paced %s; wait at least %.0f ms between sends' %
                                (app, self.gap_s * 1000))
                return
            # Reserve *before* scheduling the coroutine: two rapid button
            # presses cannot race past the outstanding count check.
            self._seq += 1
            reservation_id = self._seq
            self._reservations[app].append(dict(id=reservation_id, token=None))
            self._last_send = now
        try:
            self.backend.send(app)
        except Exception:
            with self._lock:
                q = self._reservations[app]
                res = next((r for r in q if r['id'] == reservation_id), None)
                if res is not None:
                    q.remove(res)
            raise
