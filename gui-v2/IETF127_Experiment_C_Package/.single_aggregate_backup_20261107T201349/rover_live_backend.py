#!/usr/bin/env python3
"""Non-invasive adapter for the user's existing Rover CoAP/AAP2 Python engine.

No daemon starts/stops, no FIB configuration, no link manipulation, no TCPCL changes.
Uses two existing AAP2 client endpoints, only after the old GUI is closed.

One-way delay, true uplink throughput, protocol overhead and satellite wait
are intentionally NOT inferred from Rover-only data. They must come from
separately verified Earth/Satellite timestamp and capture telemetry JSONL.
"""
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import threading
import time


class LiveBackend:
    def __init__(self, bridge, engine_path, socket_path, sol=42):
        self.b = bridge
        self.engine_path = Path(engine_path).expanduser().resolve()
        self.socket_path = socket_path
        self.sol = sol
        self.stop_event = None
        self.loop = None
        self.mods = {}
        self.ready = set()
        self.lock = threading.Lock()
        self.pending = {}  # (app, tokenhex) -> {queued_ns, submitted_ns, bytes}
        self.thread = threading.Thread(target=self._thread_main, daemon=True)

    def start(self):
        if not self.engine_path.is_file():
            self.b.log("ERROR", f"Working Rover engine file not found: {self.engine_path}")
            return
        self.thread.start()

    def stop(self):
        if self.loop is not None and self.stop_event is not None:
            try:
                self.loop.call_soon_threadsafe(self.stop_event.set)
            except RuntimeError:
                pass

    def _thread_main(self):
        try:
            asyncio.run(self._runner())
        except Exception as exc:
            self.b.log("ERROR", f"Live Rover adapter stopped: {type(exc).__name__}: {exc}")

    def _load(self, app):
        """Load two independent instances, preserving engine aggregation settings."""
        spec = importlib.util.spec_from_file_location(f"rover_draft05_live_{app}", self.engine_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load engine: {self.engine_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in ("load_mid_state", "queue_coap_request", "coap_receive_loop"):
            if not hasattr(mod, name):
                raise RuntimeError(f"Incompatible Rover engine: missing {name}")
        return mod

    async def _runner(self):
        from ud3tn_utils.aap2 import AAP2AsyncUnixClient
        self.loop = asyncio.get_running_loop()
        self.stop_event = asyncio.Event()
        tasks = []
        try:
            async with AsyncExitStack() as stack:
                for app, agentid in (("safety", "10"), ("science", "11")):
                    mod = self._load(app)
                    # The two apps must not share their MID state. Keep each app's
                    # existing on-disk MID file where already set by the engine.
                    # Point to app-specific state only if the default path collides.
                    if any(getattr(mod, "MID_STATE_FILE", None) == getattr(existing, "MID_STATE_FILE", None)
                           for existing in self.mods.values()):
                        previous = Path(mod.MID_STATE_FILE)
                        mod.MID_STATE_FILE = str(previous.with_name(previous.stem + "_" + app + previous.suffix))
                    mod.load_mid_state()
                    mod.EVENT_CALLBACK = lambda kind, fields, a=app: self._engine_event(a, kind, fields)
                    sender = await stack.enter_async_context(AAP2AsyncUnixClient(self.socket_path))
                    secret = await sender.configure(agent_id=agentid)
                    receiver = await stack.enter_async_context(AAP2AsyncUnixClient(self.socket_path))
                    await receiver.configure(agent_id=agentid, subscribe=True, secret=secret)
                    mod.coap_send_client = sender
                    mod.coap_receive_client = receiver
                    self.mods[app] = mod
                    tasks.append(asyncio.create_task(mod.coap_receive_loop()))
                    self.ready.add(app)
                    self.b.registered(app, eid=f"ipn:0.1.{agentid}")
                    self.b.log("AAP2", f"{app.upper()} registered at ipn:0.1.{agentid}; original engine unchanged")
                self.b.log("INFO", "LIVE backend: no simulated performance data; N/A requires evidence")
                await self.stop_event.wait()
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.ready.clear()

    def send(self, app):
        if app not in self.ready or self.loop is None:
            self.b.log("ERROR", f"{app}: AAP2 is not registered")
            return
        try:
            asyncio.run_coroutine_threadsafe(self._send(app), self.loop)
        except RuntimeError as exc:
            self.b.log("ERROR", str(exc))

    async def _send(self, app):
        mod = self.mods[app]
        if hasattr(mod, "nstart_space_available") and not mod.nstart_space_available():
            self.b.log("INFO", f"{app}: NSTART limit reached; request not submitted")
            return
        try:
            if app == "safety":
                await mod.queue_coap_request("get", resource_path="mission/safety-guidance")
            else:
                observation = {
                    "sol": self.sol,
                    "type": "science_observation",
                    "source": "simulated Mars rover",
                    "navigation_camera": "dust obscures distant landmarks",
                    "atmospheric_dust_index": 0.87,
                    "battery_percent": 68,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
                payload = json.dumps(observation, separators=(",", ":")).encode("utf-8")
                await mod.queue_coap_request("post", resource_path="science/observations", payload=payload)
                self.b.log("COAP", f"Science JSON generated: {len(payload)} B (simulated sensor content)")
            # IMPORTANT: DO NOT flush here. Existing engine's NSTART,
            # BUFFER_LIMIT and aggregation timer control Single vs Aggregate.
        except Exception as exc:
            self.b.log("ERROR", f"{app}: request error: {type(exc).__name__}: {exc}")

    def _engine_event(self, app, event, data):
        data = dict(data or {})
        if event == "queued":
            token = str(data.get("token", ""))
            with self.lock:
                self.pending[(app, token)] = {"queued_ns": time.monotonic_ns(), "submitted_ns": None}
            self.b.request_sent(app, method=str(data.get("method", "")),
                                uri=data.get("uri"), token=token,
                                mid=data.get("mid"), msg_type="NON")
            self.b.log("COAP", f"{app}: queued MID={data.get('mid')} token={token}")
        elif event == "submitted":
            submitted_ns = time.monotonic_ns()
            tokens = [str(t) for t in data.get("tokens", [])]
            with self.lock:
                for token in tokens:
                    p = self.pending.setdefault((app, token), {})
                    p["submitted_ns"] = submitted_ns
                    p["bp_payload_bytes"] = data.get("bytes")
            self.b.submitted(app, tokens=tokens, bundle_bytes=data.get("bytes"),
                             bundle_kind=data.get("bundle_kind"))
            self.b.log("AAP2", f"{app}: {data.get('bundle_kind')} locally submitted; "
                     f"BP payload={data.get('bytes')} B; Earth delivery not yet verified")
        elif event == "response":
            token = str(data.get("token", ""))
            matched = bool(data.get("matched")) and str(data.get("src")) == "ipn:0.3.64"
            now_ns = time.monotonic_ns()
            with self.lock:
                p = self.pending.pop((app, token), None) if matched else None
            start_ns = p.get("submitted_ns") if p else None
            rtt_ms = (now_ns - start_ns) / 1e6 if start_ns is not None else None
            self.b.response_received(app, str(data.get("code", "")), payload=data.get("payload"),
                                     rtt_ms=rtt_ms, matched=matched, token=token)
            if matched:
                self.b.log("COAP", f"{app}: matched Earth reply token={token}; "
                           f"local response interval={rtt_ms:.2f} ms" if rtt_ms is not None else
                           f"{app}: matched Earth reply token={token}, response interval N/A")
                # Application RTT is a Rover-local interval, NOT one-way delay.
                self.b.metrics(app, source="Rover local response event",
                               details={"token": token, "application_rtt_ms": rtt_ms,
                                        "note": "Rover's local response interval, not one-way delay"})
            else:
                self.b.log("ERROR", f"{app}: unmatched/untrusted response token={token}; not counted")
        elif event in ("rejected", "error", "blocked", "compat_warning", "timeout"):
            self.b.log("ERROR" if event in ("error", "rejected") else "INFO",
                       f"{app}: {event}: {data.get('message') or data.get('reason') or data}")
        else:
            self.b.log("INFO", f"{app}: engine event {event}")


class MetricsFeed:
    """Read externally verified Earth/Satellite measurements, never simulated locally.

    Each JSON line is one experiment record with raw timestamps and byte counts.
    Unknown/insufficient values remain N/A. The collector that produces these
    records is separate from the GUI and must be independently validated.
    """
    def __init__(self, bridge, path):
        self.bridge, self.path = bridge, Path(path).expanduser()
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stopping.set()

    @staticmethod
    def _seconds(a, b):
        if not (a and b):
            return None
        def parsed(x):
            if isinstance(x, (float, int)):
                return float(x)
            return datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()
        try:
            return parsed(b) - parsed(a)
        except (ValueError, TypeError, OverflowError):
            return None

    def _handle(self, item):
        if not isinstance(item, dict) or item.get("app") not in ("safety", "science"):
            return
        app = item["app"]
        origin = item.get("source", "External testbed evidence")
        uncertainty_ms = item.get("clock_uncertainty_ms")
        # A one-way measurement is valid only with times from both machines,
        # an explicit clock-uncertainty estimate, and no time jumps within run.
        d = self._seconds(item.get("rover_submit_utc"), item.get("earth_recv_utc"))
        validated = (isinstance(uncertainty_ms, (int, float)) and 0 <= uncertainty_ms <= 20 and
                     item.get("clock_checked") is True and item.get("clock_stepped_during_run") is False)
        delay_ms = round(d * 1000, 4) if d is not None and d >= 0 and validated else None
        if d is not None and delay_ms is None:
            self.bridge.log("INFO", "One-way delay held N/A: clock-quality evidence absent/invalid")
        wait_sec = None
        if item.get("satellite_receive_monotonic_ns") is not None and item.get("satellite_forward_monotonic_ns") is not None:
            wait_sec = (item["satellite_forward_monotonic_ns"] - item["satellite_receive_monotonic_ns"]) / 1e9
        elif item.get("satellite_receive_utc") and item.get("satellite_forward_utc"):
            wait_sec = self._seconds(item["satellite_receive_utc"], item["satellite_forward_utc"])
        wait_ms = wait_sec * 1000 if wait_sec is not None and wait_sec >= 0 else None
        # Sustained throughput requires an explicit fixed window, not the
        # ~0.88ms arrival span of a single three-segment packetization.
        window = item.get("window_seconds")
        traffic_bytes = item.get("window_received_bytes")
        throughput = (8 * traffic_bytes / (1000 * window)
                      if isinstance(window, (int, float)) and window >= 1.0 and
                         isinstance(traffic_bytes, (int, float)) and traffic_bytes >= 0 else None)
        useful = item.get("json_bytes")
        captured = item.get("associated_captured_frame_bytes")
        overhead = (captured - useful
                    if isinstance(useful, (int, float)) and isinstance(captured, (int, float)) and
                       captured >= useful >= 0 and item.get("frame_association_verified") is True else None)
        delivered, sent = item.get("earth_received_count"), item.get("rover_submitted_count")
        if not (isinstance(delivered, int) and isinstance(sent, int) and 0 <= delivered <= sent):
            delivered = sent = None
        self.bridge.metrics(app, delay_ms=delay_ms, throughput_kbps=throughput,
                            overhead_b=overhead, storage_wait_ms=wait_ms,
                            delivered=delivered, sent=sent, layers=item.get("layers"),
                            source=origin,
                            delivery_evidence="earth_receipt" if delivered is not None else None,
                            clock_quality=uncertainty_ms, details=item)

    def _run(self):
        # Follow data appended AFTER starting the GUI. Existing historical
        # data are not treated as this run's live metrics.
        pos = self.path.stat().st_size if self.path.exists() else 0
        while not self._stopping.wait(0.5):
            try:
                if not self.path.exists():
                    continue
                size = self.path.stat().st_size
                if size < pos:
                    pos = 0
                with self.path.open(encoding="utf-8") as f:
                    f.seek(pos)
                    while True:
                        line = f.readline()
                        if not line:
                            break
                        if not line.endswith("\n"):
                            break  # don't read partial JSON line
                        pos = f.tell()
                        try:
                            item = json.loads(line)
                            self._handle(item)
                        except (json.JSONDecodeError, ValueError, TypeError) as exc:
                            self.bridge.log("ERROR", f"Invalid metrics JSONL line: {exc}")
            except OSError as exc:
                self.bridge.log("ERROR", f"Metrics feed cannot read file: {exc}")
