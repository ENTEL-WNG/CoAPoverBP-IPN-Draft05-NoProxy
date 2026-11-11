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


class CoAPPayloadSubmissionAudit:
    """Observe the existing application-layer encoder at its AAP2 handoff.

    No protocol objects are constructed or modified here.  We compare the
    exact BP payload byte string that NodeA hands to µD3TN with a fresh
    encoding of the CURRENT NodeA application CoAP buffer.
    """

    def __init__(self, sender, module, bridge, app):
        self.sender, self.module, self.bridge, self.app = sender, module, bridge, app
        self.last_report = None

    def __getattr__(self, name):
        return getattr(self.sender, name)

    def verify(self, bundle_payload):
        messages = list(getattr(self.module, "coap_buffer", ()))
        if not messages:
            raise ValueError("NodeA application buffer empty at AAP2 transmission: cannot verify kind")
        if not isinstance(bundle_payload, (bytes, bytearray)):
            raise ValueError("NodeA BP payload is not raw bytes")
        n = len(messages)
        if n not in (1, 2):
            raise ValueError(f"Expected 1 or 2 CoAP messages for controlled test; observed {n}")
        if n == 2 and int(getattr(self.module, "NSTART", 1)) < 2:
            raise ValueError("Aggregate would exceed NodeA's configured NSTART")
        if len({bytes(m.token) for m in messages}) != n or len({int(m.mid) for m in messages}) != n:
            raise ValueError("CoAP members do not have distinct Token and MID")
        lengths = []
        encoded = []
        for i, message in enumerate(messages, 1):
            # aiocoap's option is part of the existing engine's actual message.
            option = message.opt.payload_length
            if n == 1:
                if option is not None:
                    raise ValueError("Single illegally has a Payload-length option")
                lengths.append(None)
            else:
                value = len(message.payload)
                if not isinstance(option, int) or option != value:
                    raise ValueError(f"Aggregate member {i} Payload-length={option!r}, actual payload={value} B")
                lengths.append(option)
            encoded.append(message.encode())
        expected = b"".join(encoded)
        if expected != bytes(bundle_payload):
            raise ValueError("App-buffer CoAP serialization differs from the actual AAP2 BP payload")
        report = {
            "kind": "SINGLE" if n == 1 else "AGGREGATE",
            "members": n,
            "lengths": lengths,
            "mids": [int(m.mid) for m in messages],
            "tokens": [bytes(m.token).hex() for m in messages],
            "bp_bytes": len(bundle_payload),
            "nstart": int(getattr(self.module, "NSTART", 1)),
        }
        return report

    async def send_adu_rpc(self, *args, **kwargs):
        # Standard NodeA invocation is (BundleADU, bytes).  Verify before
        # handing bytes to µD3TN.  This deliberately does NOT change payload.
        if len(args) >= 2:
            raw = args[1]
        else:
            raw = kwargs.get("bundle_payload", kwargs.get("payload"))
        report = self.verify(raw)
        result = await self.sender.send_adu_rpc(*args, **kwargs)
        self.last_report = report
        # Confirmation is tied to successful AAP2 RPC, not merely a button click.
        a = self.app.upper()
        if report["members"] == 1:
            self.bridge.log("COAP", f"{a} APPLICATION LAYER: SINGLE verified in submitted BP payload; Payload-length option ABSENT; MID={report['mids'][0]} Token={report['tokens'][0]}; {report['bp_bytes']} B")
        else:
            self.bridge.log("COAP", f"{a} APPLICATION-LAYER AGGREGATION verified: {report['members']} CoAP NON messages concatenated BEFORE BPv7; one AAP2 bundle submission; NSTART={report['nstart']}")
            for i, length in enumerate(report["lengths"]):
                self.bridge.log("COAP", f"  Aggregate member #{i+1}: MID={report['mids'][i]} Token={report['tokens'][i]} Payload-length option={length} B (encoded and checked)")
        return result


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
        self.aggregate_batches = {}  # app -> {all tokens, remaining tokens}
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
                    # Read-only serialization witness: checks ACTUAL bytes at
                    # the CoAP application -> BP/AAP2 boundary.
                    mod.coap_send_client = CoAPPayloadSubmissionAudit(sender, mod, self.b, app)
                    mod.coap_receive_client = receiver
                    self.mods[app] = mod
                    self.b.log("INFO", f"{app.upper()} NodeA engine NSTART={getattr(mod, 'NSTART', 'unknown')}, "
                               f"BUFFER_LIMIT={getattr(mod, 'BUFFER_LIMIT', 'unknown')}; "
                               "application-layer aggregation; Satellite is BP relay only")
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
        """Existing GUI send button: exactly one Single (no buffer timer wait)."""
        if app not in self.ready or self.loop is None:
            self.b.log("ERROR", f"{app}: AAP2 is not registered")
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._send(app), self.loop)
            fut.add_done_callback(lambda f: self._report_future(app, "Single", f))
        except RuntimeError as exc:
            self.b.log("ERROR", str(exc))

    def send_aggregate(self, app):
        """Safety-only, two Singles from ONE source EID to ONE Earth EID."""
        if app != "safety":
            self.b.log("ERROR", "Aggregate demo uses only Safety ipn:0.1.10")
            return
        if app not in self.ready or self.loop is None:
            self.b.log("ERROR", "Safety AAP2 is not registered")
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._send_aggregate(app), self.loop)
            fut.add_done_callback(lambda f: self._report_future(app, "Aggregate", f))
        except RuntimeError as exc:
            self.b.log("ERROR", str(exc))

    def _report_future(self, app, kind, future):
        try:
            future.result()
        except Exception as exc:
            self.b.log("ERROR", f"{app} {kind} coroutine failed: {type(exc).__name__}: {exc}")

    async def _send(self, app):
        """Single is explicitly flushed; do not infer Single from a timer."""
        mod = self.mods[app]
        if not hasattr(mod, "flush_coap_buffer"):
            self.b.log("ERROR", "NodeA missing flush_coap_buffer; cannot force Single")
            return
        if getattr(mod, "coap_buffer", []):
            self.b.log("ERROR", f"{app}: existing CoAP buffer not empty; Single not sent")
            return
        if hasattr(mod, "nstart_space_available") and not mod.nstart_space_available():
            self.b.log("INFO", f"{app}: NSTART limit reached; Single not sent")
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
            if len(getattr(mod, "coap_buffer", [])) != 1:
                self.b.log("ERROR", f"{app}: expected exactly 1 queued Single; not flushing")
                return
            await mod.flush_coap_buffer()
        except Exception as exc:
            self.b.log("ERROR", f"{app}: Single error: {type(exc).__name__}: {exc}")

    async def _send_aggregate(self, app):
        """Force exactly two NON GET Singles in one AAP2 bundle submission.

        Neither NSTART nor BUFFER_LIMIT is raised here. Existing engine and
        GUI gate must ALREADY permit two interactions. This is only a
        functional test, not a congestion-control safety certification.
        """
        mod = self.mods[app]
        needed = ("queue_coap_request", "flush_coap_buffer", "nstart_space_available")
        missing = [n for n in needed if not hasattr(mod, n)]
        if missing:
            self.b.log("ERROR", f"Aggregate incompatible engine: missing {missing}")
            return
        nstart = getattr(mod, "NSTART", 1)
        capacity = getattr(mod, "BUFFER_LIMIT", 0)
        if nstart < 2 or capacity < 2:
            self.b.log("ERROR", f"Aggregate requires preconfigured NSTART>=2 and BUFFER_LIMIT>=2; got {nstart}, {capacity}")
            return
        if getattr(mod, "coap_buffer", []) or getattr(mod, "pending_requests", {}):
            self.b.log("INFO", "Aggregate requires empty Safety buffer and no previous outstanding Safety requests")
            return
        if hasattr(mod, "current_interaction_count") and mod.current_interaction_count() != 0:
            self.b.log("INFO", "Aggregate blocked: outstanding Safety interactions detected")
            return
        try:
            # Both requests are generated sequentially in the same event loop
            # and share mod.coap_send_client / agent_id=10, not Science agent_id=11.
            for index in (1, 2):
                if not mod.nstart_space_available():
                    self.b.log("ERROR", f"Aggregate stopped: NSTART exhausted before member {index}")
                    return
                await mod.queue_coap_request("get", resource_path="mission/safety-guidance")
            # With BUFFER_LIMIT=2 the engine already flushed on second queue.
            # For BUFFER_LIMIT>2 manually flush BOTH before timer expiry.
            pending = len(getattr(mod, "coap_buffer", []))
            if pending == 2:
                await mod.flush_coap_buffer()
            elif pending != 0:
                self.b.log("ERROR", f"Unexpected buffer count {pending}; cannot claim Aggregate")
                return
            self.b.log("INFO", "Aggregate action queued 2 Safety requests; confirm AGGREGATE (2 Singles) submission and two replies in log")
        except Exception as exc:
            self.b.log("ERROR", f"Aggregate generation failed: {type(exc).__name__}: {exc}")

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
            # BP lifetime belongs to the encapsulating bundle, not to CoAP
            # member Payload-length.  Engine callback reports *requested* life.
            lifetime = data.get("lifetime_ms")
            if isinstance(lifetime, (int, float)):
                self.b.log("BP", f"{app.upper()}: BPv7 encapsulating bundle lifetime REQUESTED={lifetime / 1000:g} s ({int(lifetime)} ms)")
                mod = self.mods.get(app)
                try:
                    non_life = float(mod.NON_LIFETIME_SECONDS)
                    delay = float(mod.MAX_AGGR_DELAY_SECONDS)
                    if str(data.get("bundle_kind", "")).lower() == "aggregate":
                        expected = max(0., non_life - delay) * 1000
                        rule = "NON_LIFETIME - MAX_AGGR_DELAY"
                    else:
                        expected = non_life * 1000
                        rule = "NON_LIFETIME"
                    if abs(float(lifetime) - expected) > 0.5:
                        self.b.log("ERROR", f"{app.upper()}: DRAFT-05 BP lifetime mismatch: requested={lifetime:g} ms, expected={expected:g} ms ({rule}); check NodeA; DO NOT claim lifetime compliance")
                    else:
                        self.b.log("BP", f"{app.upper()}: Draft-05 NON BP lifetime check PASS ({rule})")
                except (AttributeError, ValueError, TypeError):
                    self.b.log("INFO", f"{app.upper()}: cannot independently validate Draft-05 lifetime: engine constants unavailable")
            else:
                self.b.log("INFO", f"{app.upper()}: BP bundle lifetime not provided by engine callback; not verified")
            audit = getattr(getattr(self.mods.get(app), "coap_send_client", None), "last_report", None)
            if audit is None or audit.get("members") != len(tokens) or set(audit.get("tokens", [])) != set(tokens):
                self.b.log("ERROR", f"{app.upper()}: application-layer Payload-length evidence does not match submission callback")
            if str(data.get("bundle_kind", "")).lower() == "aggregate" and len(tokens) == 2:
                self.aggregate_batches[app] = {
                    "all": set(tokens), "remaining": set(tokens)
                }
                self.b.log("COAP", f"{app}: AGGREGATE submitted: exactly 2 member tokens; awaiting 2 Earth replies")
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
            batch = self.aggregate_batches.get(app)
            if matched and batch and token in batch["remaining"]:
                batch["remaining"].remove(token)
                done = len(batch["all"]) - len(batch["remaining"])
                self.b.log("COAP", f"{app}: AGGREGATE matched Earth reply {done}/2 token={token}")
                if not batch["remaining"]:
                    self.b.log("COAP", f"{app}: AGGREGATE response test PASS (2/2 matched)")
                    self.aggregate_batches.pop(app, None)
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
