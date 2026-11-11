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
        if max_outstanding not in (1, 2, 3, 4):
            raise ValueError('GUI supports NSTART 1..4; increases above 1 require explicit authorization')
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

    def send(self, app, mode="single"):
        """One click reserves exactly one outstanding interaction, even if buffered."""
        if app not in self._reservations:
            return
        if mode not in ("single", "aggregate"):
            self.bridge.log('ERROR', f"Unknown GUI transmission mode: {mode}")
            return
        with self._lock:
            if app not in self.backend.ready or app not in self.backend.mods:
                self.bridge.log('INFO', f'{app}: awaiting AAP2 registration')
                return
            mod = self.backend.mods[app]
            engine_nstart = int(getattr(mod, 'NSTART', 1))
            if self.limit > engine_nstart:
                self.bridge.log('ERROR', f'{app}: configured GUI limit {self.limit} exceeds NodeA NSTART={engine_nstart}')
                return
            if mode == 'aggregate' and self.limit < 2:
                self.bridge.log('ERROR', 'CONGESTION CONTROL: Aggregate requires NSTART >= 2; current approved GUI limit is 1. No request queued.')
                return
            app_used = len(self._reservations[app]); shared_used = sum(len(q) for q in self._reservations.values())
            if app_used >= self.limit or shared_used >= self.limit:
                self.bridge.log('ERROR', f'CONGESTION CONTROL: NSTART={self.limit} limit reached — '
                                f'{app_used}/{self.limit} {app} outstanding, {shared_used}/{self.limit} shared; '
                                'request rejected. Wait for matched Earth replies.')
                return
            now = time.monotonic()
            # Pacing applies to individual Single submissions. Multiple clicks
            # in Aggregate mode create no additional link traffic until flush.
            if mode == 'single' and now - self._last_send < self.gap_s:
                self.bridge.log('INFO', f'CONGESTION CONTROL: wait {self.gap_s*1000:.0f} ms between Singles')
                return
            self._seq += 1
            reservation_id = self._seq
            self._reservations[app].append(dict(id=reservation_id, token=None))
            if mode == 'single': self._last_send = now
        try:
            future = self.backend.send(app, mode=mode)
            if future is None:
                self._release_failed(app, reservation_id)
                return
            if hasattr(future, 'add_done_callback'):
                def complete(f):
                    try:
                        succeeded = f.result()
                    except Exception as exc:
                        self.bridge.log('ERROR', f'{app}: send task failed: {exc}')
                        succeeded = False
                    if succeeded is False:
                        self._release_failed(app, reservation_id)
                future.add_done_callback(complete)
        except Exception:
            self._release_failed(app, reservation_id)
            raise

    def _release_failed(self, app, reservation_id):
        with self._lock:
            q = self._reservations[app]
            res = next((r for r in q if r['id'] == reservation_id), None)
            if res is not None: q.remove(res)
