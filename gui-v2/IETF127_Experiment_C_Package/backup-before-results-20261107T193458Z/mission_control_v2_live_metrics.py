#!/usr/bin/env python3
"""
Mars Rover Mission Control - evidence-aware CoAP over BPv7 dashboard (Tkinter)
=====================================================================

Target: draft-ietf-core-coap-bp-05, IPN dual-application experiment
Topology: ROVER ipn:0.1.0  ->  SATELLITE ipn:0.2.0 (uD3TN relay)  ->  EARTH ipn:0.3.64
Apps:     Safety  GET  /safety   from ipn:0.1.10
          Science POST /science  from ipn:0.1.11

Run the built-in simulator (no uD3TN needed):
    python3 mission_control_v2.py --demo
    python3 mission_control_v2.py --demo --banner rover.jpg      # optional photo strip (needs Pillow)

Hooking up your real backend
----------------------------
The GUI never touches the network. Your AAP2 / aiocoap code runs in its own
thread and pushes events through a MissionBridge (thread-safe queue):

    import asyncio, threading
    from mission_control import MissionBridge, MissionControl

    bridge = MissionBridge()
    loop = asyncio.new_event_loop()

    async def send(app):                       # app is "safety" or "science"
        bridge.request_sent(app, payload=..., mid=..., token=...)
        resp = await ...                        # your CoAP-over-BP exchange
        bridge.response_received(app, "2.01 Created", payload=..., location=..., rtt_ms=...)
        bridge.metrics(app, delay_ms=..., throughput_kbps=..., overhead_b=...,
                       storage_wait_ms=..., delivered=..., sent=...,
                       layers={"CoAP": 18, "BPv7": 112, "TCPCL": 32, "TCP": 84, "IP": 56, "Ethernet": 48})

    threading.Thread(target=loop.run_forever, daemon=True).start()
    bridge.registered("safety");  bridge.registered("science")

    MissionControl(bridge,
                   on_send=lambda app: asyncio.run_coroutine_threadsafe(send(app), loop),
                   mode="LIVE").mainloop()

Other events: bridge.log(category, text)  with category in
BP / COAP / AAP2 / METRICS / LINK / ERROR / INFO, and bridge.link("sat-earth", up=False).

Keys: S = send Safety, C = send Science, L = toggle Sat-Earth link (demo), F11 = full screen.
"""

import argparse
import csv
import json
import math
import os
import queue
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from tkinter import font as tkfont

# --------------------------------------------------------------------------- theme
T = dict(
    bg="#0a101d", panel="#111a2c", panel2="#162238", border="#223152",
    text="#e7edf7", muted="#8797b3", faint="#4b5a78",
    teal="#19b5a5", teal_dk="#0f6f66", orange="#f0872a", orange_dk="#8f4f17",
    ok="#2fca6b", warn="#f2b33d", bad="#ef4f4f", link="#3d7ea6", bp="#6aa8ff",
    mars="#3a1c13", earth="#0f2c4f",
)

APPS = {
    "safety":  dict(name="ROVER SAFETY",  method="GET",  path="/mission/safety-guidance",  eid="ipn:0.1.10",
                    color=T["teal"], dark=T["teal_dk"], key="S"),
    "science": dict(name="ROVER SCIENCE", method="POST", path="/science/observations", eid="ipn:0.1.11",
                    color=T["orange"], dark=T["orange_dk"], key="C"),
}
EARTH_EID = "ipn:0.3.64"
COAP_URI_AUTHORITY = "64.3.0.ipn.alt"
NODES = {
    "rover": ("ROVER", "ipn:0.1.0"),
    "sat":   ("SATELLITE", "ipn:0.2.0"),
    "earth": ("EARTH", EARTH_EID),
}
LAYER_COLORS = {"CoAP": "#f0872a", "BPv7": "#6aa8ff", "TCPCL": "#9b7bff",
                "TCP": "#19b5a5", "IP": "#4fa3c7", "Ethernet": "#6b7a99"}
LOG_COLORS = {"BP": T["bp"], "COAP": T["orange"], "AAP2": T["teal"], "METRICS": "#c9a7ff",
              "LINK": T["warn"], "ERROR": T["bad"], "INFO": T["muted"]}

# value thresholds: (warn, bad, higher_is_worse)
THRESHOLDS = {
    "delay_ms":        (500, 2000, True),
    "throughput_kbps": (0.20, 0.05, False),
    "overhead_b":      (400, 600, True),
    "storage_wait_ms": (500, 5000, True),
    "delivery_pct":    (100, 90, False),
}

MOVE_MS = 900      # visual time for one hop
HOLD_MS = 420      # visual minimum dwell at the satellite


def grade(metric, v):
    warn, bad, hi_worse = THRESHOLDS[metric]
    if hi_worse:
        return "bad" if v >= bad else "warn" if v >= warn else "ok"
    return "bad" if v < bad else "warn" if v < warn else "ok"


# --------------------------------------------------------------------------- bridge
class MissionBridge:
    """Thread-safe event channel from the protocol backend to the GUI."""

    def __init__(self):
        self._q = queue.Queue()

    def _put(self, kind, **kw):
        kw["ts"] = time.time()
        self._q.put((kind, kw))

    def registered(self, app, eid=None):
        self._put("registered", app=app, eid=eid or APPS[app]["eid"])

    def request_sent(self, app, payload=None, msg_type="NON", mid=None, token=None,
                     method=None, uri=None):
        self._put("request", app=app, payload=payload, msg_type=msg_type, mid=mid, token=token,
                  method=method or APPS[app]["method"],
                  uri=uri or f"coap://{COAP_URI_AUTHORITY}{APPS[app]['path']}")

    def response_received(self, app, code, payload=None, location=None, rtt_ms=None,
                          matched=False, token=None):
        self._put("response", app=app, code=code, payload=payload,
                  location=location, rtt_ms=rtt_ms, matched=matched, token=token)

    def submitted(self, app, tokens=None, bundle_bytes=None, bundle_kind=None):
        self._put("submitted", app=app, tokens=tokens or [],
                  bundle_bytes=bundle_bytes, bundle_kind=bundle_kind)

    def metrics(self, app, *, delay_ms=None, throughput_kbps=None, overhead_b=None,
                storage_wait_ms=None, delivered=None, sent=None, layers=None,
                source="unspecified", delivery_evidence=None, details=None,
                clock_quality=None):
        """None means unmeasured, never zero. Evidence must be provided for live ratios."""
        self._put("metrics", app=app, delay_ms=delay_ms, throughput_kbps=throughput_kbps,
                  overhead_b=overhead_b, storage_wait_ms=storage_wait_ms,
                  delivered=delivered, sent=sent, layers=layers,
                  source=source, delivery_evidence=delivery_evidence,
                  details=details or {}, clock_quality=clock_quality)

    def link(self, link_id, up):
        self._put("link", link_id=link_id, up=bool(up))

    def log(self, category, message):
        self._put("log", category=category.upper(), message=message)

    def drain(self):
        while True:
            try:
                yield self._q.get_nowait()
            except queue.Empty:
                return


# --------------------------------------------------------------------------- demo backend
class DemoBackend:
    """Simulates the three-node uD3TN lab so the GUI can be shown without it."""

    def __init__(self, bridge, sol=42):
        self.b = bridge
        self.sol = sol
        self.links = {"rover-sat": True, "sat-earth": True}
        self.sent = {a: 0 for a in APPS}
        self.delivered = {a: 0 for a in APPS}
        self.lock = threading.Lock()
        self.science_seq = 2
        threading.Thread(target=self._boot, daemon=True).start()

    def _boot(self):
        self.b.log("INFO", "Demo backend started (simulated uD3TN nodes)")
        for app in APPS:
            time.sleep(0.4)
            self.b.log("AAP2", f"{app.upper()}: AAP2 registered {APPS[app]['eid']}")
            self.b.registered(app)
        self.b.log("INFO", "Both independent IPN CoAP endpoints ready")

    def toggle_link(self, link_id):
        self.links[link_id] = not self.links[link_id]
        state = "UP" if self.links[link_id] else "DOWN (contact lost)"
        self.b.link(link_id, self.links[link_id])
        self.b.log("LINK", f"{link_id} link {state}")

    def send(self, app):
        threading.Thread(target=self._exchange, args=(app,), daemon=True).start()

    def _wait_link(self, link_id):
        if self.links[link_id]:
            return 0.0
        t = time.time()
        while not self.links[link_id]:
            time.sleep(0.05)
        return time.time() - t

    def _exchange(self, app):
        a = APPS[app]
        with self.lock:
            self.sent[app] += 1
            if app == "science":
                self.science_seq += 1
            seq = self.science_seq
        mid = random.randrange(1 << 24)
        token = random.randrange(1 << 16)
        if app == "science":
            payload = {"sol": self.sol, "temp_c": round(-63.4 + random.uniform(-1.5, 1.5), 1),
                       "pressure_pa": round(743.2 + random.uniform(-3, 3), 1),
                       "rad": round(0.18 + random.uniform(-0.02, 0.02), 2)}
        else:
            payload = None
        body = json.dumps(payload, separators=(",", ":")) if payload else ""
        self.b.request_sent(app, payload=payload, mid=mid, token=token)
        self.b.log("COAP", f"NON {a['method']} {a['path']}  MID 0x{mid:06X}  Tkn {token:04x}  ({len(body)} B payload)")
        self.b.log("BP", f"bundle {a['eid']} -> {EARTH_EID} submitted via AAP2")

        t0 = time.time()
        self._wait_link("rover-sat")
        time.sleep(random.uniform(0.045, 0.065))
        self.b.log("BP", "bundle received at ipn:0.2.0, held in storage")
        t_store = time.time()
        time.sleep(random.uniform(0.03, 0.05))
        outage = self._wait_link("sat-earth")
        store_ms = (time.time() - t_store) * 1000
        self.b.log("BP", f"ipn:0.2.0 forwarded bundle -> {EARTH_EID} after {store_ms:.0f} ms"
                         + (" (waited for contact)" if outage > 0 else ""))
        time.sleep(random.uniform(0.045, 0.065))
        one_way_ms = (time.time() - t0) * 1000
        self.b.log("COAP", f"EARTH server: {a['method']} {a['path']} received")

        # response
        time.sleep(0.008)
        if app == "science":
            code, location = "2.01 Created", f"/science/sol{self.sol}-{seq:04d}"
            rpayload = {"result": "stored", "id": f"sol{self.sol}-{seq:04d}"}
        else:
            code, location = "2.05 Content", None
            rpayload = {"state": "nominal", "battery_pct": random.randint(78, 84),
                        "tilt_deg": round(random.uniform(1.0, 3.5), 1), "hazard": False}
        self._wait_link("sat-earth")
        time.sleep(random.uniform(0.045, 0.065))
        time.sleep(random.uniform(0.02, 0.04))
        self._wait_link("rover-sat")
        time.sleep(random.uniform(0.045, 0.065))
        rtt_ms = (time.time() - t0) * 1000
        with self.lock:
            self.delivered[app] += 1
            d, s = self.delivered[app], self.sent[app]
        self.b.response_received(app, code, payload=rpayload, location=location, rtt_ms=rtt_ms, matched=True)
        self.b.log("COAP", f"{code} <- {EARTH_EID}  RTT {rtt_ms:.0f} ms")

        layers = {"CoAP": 14 + (4 if payload else 0), "BPv7": 112, "TCPCL": 32,
                  "TCP": 84, "IP": 56, "Ethernet": 48}
        thr = 8 * (len(body) or 48) / (one_way_ms / 1000) / 1000  # simulated kbps
        self.b.metrics(app, delay_ms=one_way_ms, throughput_kbps=thr, overhead_b=sum(layers.values()),
                       storage_wait_ms=store_ms, delivered=d, sent=s, layers=layers,
                       source="SIMULATED DEMO", delivery_evidence="simulation",
                       details={"warning": "Synthetic demonstration values, not a packet capture"})
        self.b.log("METRICS", f"{app}: SIMULATED delay {one_way_ms:.0f} ms | simulated rate {thr:.2f} kbps | "
                              f"store {store_ms:.0f} ms | delivered {d}/{s}")


# --------------------------------------------------------------------------- node artwork (vector, no files needed)
def _pt(cx, cy, s):
    return lambda *uv: [v for i in range(0, len(uv), 2) for v in (cx + uv[i] * s, cy + uv[i + 1] * s)]


def draw_rover(c, cx, cy, s, tags):
    """Six-wheeled Mars rover, side view, facing right. s = bounding size in px."""
    P = _pt(cx, cy, s)
    lw = max(1, s / 34)
    c.create_oval(*P(-0.50, 0.40, 0.50, 0.48), fill="#2a120c", outline="", tags=tags)          # ground shadow
    # rocker-bogie suspension
    c.create_line(*P(-0.34, 0.32, -0.16, 0.12, 0.00, 0.32), fill="#a3acba", width=lw * 1.4, tags=tags)
    c.create_line(*P(-0.16, 0.12, 0.14, 0.10, 0.34, 0.32), fill="#a3acba", width=lw * 1.4, tags=tags)
    for wx in (-0.34, 0.0, 0.34):                                                              # wheels
        c.create_oval(*P(wx - 0.115, 0.205, wx + 0.115, 0.435), fill="#1b1f27", outline="#8a93a3", width=lw, tags=tags)
        c.create_oval(*P(wx - 0.04, 0.28, wx + 0.04, 0.36), fill="#8a93a3", outline="", tags=tags)
    # RTG power unit at the back
    c.create_polygon(*P(-0.50, 0.02, -0.37, -0.04, -0.33, 0.10, -0.46, 0.15), fill="#5b6474",
                     outline="#3a414d", width=lw, tags=tags)
    for f in (0.0, 0.05):
        c.create_line(*P(-0.49 + f, 0.04 + f / 2, -0.38 + f, -0.01 + f / 2), fill="#7d8696", width=lw, tags=tags)
    # body
    c.create_rectangle(*P(-0.37, -0.04, 0.31, 0.12), fill="#e3e7ed", outline="#9aa3b2", width=lw, tags=tags)
    c.create_rectangle(*P(-0.37, 0.06, 0.31, 0.12), fill="#b5bcc8", outline="", tags=tags)
    # high-gain antenna + UHF whip
    c.create_line(*P(-0.10, -0.04, -0.10, -0.10), fill="#9aa3b2", width=lw, tags=tags)
    c.create_oval(*P(-0.20, -0.17, 0.00, -0.08), fill="#d4d9e1", outline="#9aa3b2", width=lw, tags=tags)
    c.create_line(*P(-0.27, -0.04, -0.27, -0.26), fill="#9aa3b2", width=lw, tags=tags)
    c.create_oval(*P(-0.29, -0.29, -0.25, -0.25), fill="#f2b33d", outline="", tags=tags)
    # mast with camera head
    c.create_line(*P(0.18, -0.04, 0.18, -0.33), fill="#cfd5de", width=lw * 2.2, tags=tags)
    c.create_rectangle(*P(0.07, -0.45, 0.31, -0.32), fill="#eef1f5", outline="#9aa3b2", width=lw, tags=tags)
    c.create_oval(*P(0.22, -0.415, 0.29, -0.345), fill="#19b5a5", outline="#0f6f66", width=lw, tags=tags)
    c.create_oval(*P(0.11, -0.415, 0.18, -0.345), fill="#19b5a5", outline="#0f6f66", width=lw, tags=tags)
    # robotic arm with instrument turret
    c.create_line(*P(0.31, 0.02, 0.43, -0.06, 0.47, 0.10), fill="#b5bcc8", width=lw * 1.6, joinstyle="round", tags=tags)
    c.create_rectangle(*P(0.43, 0.10, 0.51, 0.18), fill="#f0872a", outline="#8f4f17", width=lw, tags=tags)


def draw_satellite(c, cx, cy, s, tags):
    """Relay satellite: gold-foil bus, two solar wings, dish pointing down to the surface."""
    P = _pt(cx, cy, s)
    lw = max(1, s / 40)
    c.create_line(*P(-0.20, 0.0, 0.20, 0.0), fill="#9aa3b2", width=lw * 1.6, tags=tags)       # wing booms
    for x0 in (-0.52, 0.20):                                                                  # solar wings
        c.create_rectangle(*P(x0, -0.12, x0 + 0.32, 0.12), fill="#1d3f7a", outline="#6aa8ff", width=lw, tags=tags)
        for k in range(1, 4):
            xx = x0 + k * 0.08
            c.create_line(*P(xx, -0.12, xx, 0.12), fill="#3a6fb8", width=max(1, lw * 0.7), tags=tags)
        c.create_line(*P(x0, 0.0, x0 + 0.32, 0.0), fill="#3a6fb8", width=max(1, lw * 0.7), tags=tags)
    # bus
    c.create_rectangle(*P(-0.13, -0.16, 0.13, 0.15), fill="#d4a72c", outline="#8a6d12", width=lw, tags=tags)
    for yy in (-0.07, 0.03):
        c.create_line(*P(-0.13, yy, 0.13, yy + 0.02), fill="#b08a1c", width=lw, tags=tags)
    c.create_rectangle(*P(-0.05, -0.12, 0.05, -0.04), fill="#2a2f38", outline="", tags=tags)  # sensor window
    # top antenna
    c.create_line(*P(0.0, -0.16, 0.0, -0.32), fill="#cfd5de", width=lw, tags=tags)
    c.create_oval(*P(-0.03, -0.36, 0.03, -0.30), fill="#f2b33d", outline="", tags=tags)
    # dish (to Mars surface) + feed
    c.create_line(*P(0.0, 0.15, 0.0, 0.21), fill="#9aa3b2", width=lw, tags=tags)
    c.create_arc(*P(-0.16, 0.13, 0.16, 0.37), start=180, extent=180, style="chord",
                 fill="#e6e9ef", outline="#9aa3b2", width=lw, tags=tags)
    c.create_oval(*P(-0.025, 0.30, 0.025, 0.35), fill="#9aa3b2", outline="", tags=tags)
    # signal arcs toward Earth (right)
    for r in (0.10, 0.17):
        c.create_arc(*P(0.46 - r, -0.30 - r, 0.46 + r, -0.30 + r), start=-40, extent=80, style="arc",
                     outline="#6aa8ff", width=lw, tags=tags)


def draw_earth(c, cx, cy, s, tags):
    """Earth with atmosphere glow, continents, clouds and a ground-station dish."""
    P = _pt(cx, cy, s)
    lw = max(1, s / 40)
    c.create_oval(*P(-0.47, -0.47, 0.47, 0.47), fill="", outline="#1f4f86", width=lw * 2.5, tags=tags)  # glow
    c.create_oval(*P(-0.42, -0.42, 0.42, 0.42), fill="#1b5fae", outline="#6aa8ff", width=lw, tags=tags)
    c.create_oval(*P(-0.30, -0.34, 0.14, 0.06), fill="#2470c2", outline="", tags=tags)       # sunlit side
    green = dict(fill="#3fa35b", outline="#2f8547", width=max(1, lw * 0.6), smooth=True, tags=tags)
    c.create_polygon(*P(-0.27, -0.28, -0.11, -0.31, -0.08, -0.19, -0.19, -0.10, -0.13, 0.01, -0.05, 0.09,
                        -0.09, 0.27, -0.17, 0.33, -0.21, 0.17, -0.28, 0.02, -0.33, -0.11), **green)
    c.create_polygon(*P(0.06, -0.30, 0.22, -0.28, 0.28, -0.15, 0.19, -0.08, 0.28, 0.02, 0.24, 0.19,
                        0.13, 0.30, 0.08, 0.15, 0.02, 0.01, 0.07, -0.13), **green)
    c.create_polygon(*P(-0.10, -0.40, 0.08, -0.40, 0.02, -0.34), fill="#eef4fb", outline="", smooth=True, tags=tags)
    cloud = dict(fill="#cfe2f6", outline="", smooth=True, tags=tags)
    c.create_polygon(*P(-0.36, 0.02, -0.24, -0.02, -0.12, 0.01, -0.20, 0.05), **cloud)
    c.create_polygon(*P(0.04, 0.25, 0.16, 0.22, 0.30, 0.15, 0.20, 0.25), **cloud)
    c.create_polygon(*P(0.10, -0.22, 0.24, -0.24, 0.33, -0.18, 0.20, -0.19), **cloud)
    # ground station dish, bottom-right
    c.create_line(*P(0.38, 0.47, 0.38, 0.36), fill="#cfd5de", width=lw * 1.4, tags=tags)
    c.create_polygon(*P(0.32, 0.48, 0.44, 0.48, 0.38, 0.42), fill="#9aa3b2", outline="", tags=tags)
    c.create_arc(*P(0.24, 0.20, 0.52, 0.42), start=110, extent=180, style="chord",
                 fill="#eef1f5", outline="#9aa3b2", width=lw, tags=tags)


# --------------------------------------------------------------------------- widgets
def round_rect(c, x1, y1, x2, y2, r=10, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class FlatButton(tk.Label):
    def __init__(self, master, text, command, bg, fg="#ffffff", hover=None, font=None, padx=10, pady=4):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
        self._bg, self._hover, self.command = bg, hover or bg, command
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))

    def set_colors(self, bg, hover=None):
        self._bg, self._hover = bg, hover or bg
        self.config(bg=bg)


class MetricTile(tk.Frame):
    def __init__(self, master, fonts, key, title, unit, subtitle, fmt, lower_is_better=True):
        super().__init__(master, bg=T["panel2"], highlightthickness=1, highlightbackground=T["border"])
        self.key, self.fmt, self.lower_is_better = key, fmt, lower_is_better
        self.history = []
        compact = fonts["metric"][1] < 24
        top = tk.Frame(self, bg=T["panel2"])
        top.pack(fill="x", padx=7 if compact else 12, pady=(3 if compact else 9, 0))
        tk.Label(top, text=title.upper(), bg=T["panel2"], fg=T["muted"], font=fonts["small_b"]).pack(side="left")
        self.badge = tk.Label(top, text="  -  ", bg=T["panel2"], fg=T["faint"], font=fonts["tiny_b"])
        self.badge.pack(side="right")
        mid = tk.Frame(self, bg=T["panel2"])
        mid.pack(fill="x", padx=7 if compact else 12)
        self.val = tk.Label(mid, text="--", bg=T["panel2"], fg=T["text"], font=fonts["metric"])
        self.val.pack(side="left")
        tk.Label(mid, text=unit, bg=T["panel2"], fg=T["muted"], font=fonts["body"]).pack(side="left", anchor="s", pady=(0, 2 if compact else 7), padx=(2 if compact else 4, 0))
        self.delta = tk.Label(mid, text="", bg=T["panel2"], fg=T["muted"], font=fonts["small"])
        self.delta.pack(side="right", anchor="s", pady=(0, 2 if compact else 7))
        self.sub = tk.Label(self, text=subtitle, bg=T["panel2"], fg=T["muted"], font=fonts["small"], anchor="w")
        self.sub.pack(fill="x", padx=7 if compact else 12)
        self.spark = tk.Canvas(self, height=11 if compact else 30, bg=T["panel2"], highlightthickness=0)
        self.spark.pack(fill="x", padx=7 if compact else 12,
                        pady=(1, 3) if compact else (4, 9))
        self.spark.bind("<Configure>", lambda e: self._draw_spark())

    def update_value(self, v, color, subtitle=None, provenance="MEASURED"):
        if v is None:
            self.val.config(text="N/A", fg=T["faint"])
            self.badge.config(text=" UNAVAILABLE ", fg=T["muted"])
            self.delta.config(text="")
            if subtitle is not None:
                self.sub.config(text=subtitle)
            return
        try:
            v = float(v)
        except (TypeError, ValueError):
            return
        if not math.isfinite(v):
            return
        prev = self.history[-1] if self.history else None
        self.history = (self.history + [v])[-40:]
        self.val.config(text=self.fmt(v), fg=T["text"])
        self.badge.config(text=" DEMO " if "SIMULAT" in provenance.upper() else " RECORDED ",
                          fg=T["warn"] if "SIMULAT" in provenance.upper() else T["teal"])
        if subtitle is not None:
            self.sub.config(text=subtitle)
        if prev is not None and prev != 0:
            ch = (v - prev) / abs(prev) * 100
            self.delta.config(text=f"{'▲' if ch > 0 else '▼'} {abs(ch):.0f}%" if abs(ch) >= 0.5 else "= prev",
                              fg=T["muted"])
        self._last_color = color
        self._draw_spark()

    def _draw_spark(self):
        c = self.spark
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        hs = self.history
        if w < 10:
            return
        c.create_line(0, h - 1, w, h - 1, fill=T["border"])
        if len(hs) < 2:
            c.create_text(w / 2, h / 2, text="history builds per run", fill=T["faint"], font=("TkDefaultFont", 8))
            return
        lo, hi = min(hs), max(hs)
        span = (hi - lo) or (abs(hi) or 1)
        n = len(hs)
        pts = []
        for i, v in enumerate(hs):
            x = 2 + (w - 6) * i / (n - 1)
            y = h - 4 - (h - 8) * (v - lo) / span
            pts += [x, y]
        c.create_line(*pts, fill=T["link"], width=2, smooth=True)
        x, y = pts[-2], pts[-1]
        c.create_oval(x - 3.5, y - 3.5, x + 3.5, y + 3.5, fill=getattr(self, "_last_color", T["text"]), outline="")


# --------------------------------------------------------------------------- main window
class MissionControl(tk.Tk):
    def __init__(self, bridge, on_send=None, on_toggle_link=None, mode="LIVE", sol=42, banner=None,
                 images_dir=None, event="IETF 127 Hackathon"):
        super().__init__()
        self.images_dir = images_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
        self._img_cache = {}
        self.event = event
        self.bridge, self.on_send = bridge, on_send
        self.on_toggle_link = on_toggle_link if mode == "DEMO" else None
        self.mode, self.sol = mode, sol
        self.title("Mars Rover Mission Control - CoAP over BPv7")
        self.configure(bg=T["bg"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Compact retains the original dashboard arrangement, not a scroll view.
        # At 1366x768 leave room for Ubuntu's top bar, dock and title bar.
        self.compact = (sw <= 1600 or sh <= 950)
        W = max(980, min(1500, sw - (24 if self.compact else 40)))
        H = max(520, min(940, sh - (110 if self.compact else 60)))
        self.geometry(f"{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 3)}")
        self.minsize(min(W, 980), min(H, 520))
        self.narrow = self.compact
        self.short = self.compact
        # Do not auto-maximize: the VM's usable desktop is smaller than
        # its physical display, and automatic zooming hid the bottom panels.
        self._fonts()

        self.registered = {a: False for a in APPS}
        self.links = {"rover-sat": None, "sat-earth": None} if mode != "DEMO" else {"rover-sat": True, "sat-earth": True}
        self.tokens = []
        self.flash = {}
        self.exchanges = {a: dict(req=None, resp=None) for a in APPS}
        self.app_stats = {a: dict(code="-", rtt=None, delivered=0, sent=0) for a in APPS}
        self.metric_rows = []
        self.log_rows = []
        self.log_filter = {k: tk.BooleanVar(value=True) for k in LOG_COLORS}
        self.view_app = tk.StringVar(value="science")
        self.auto_var = tk.BooleanVar(value=False)
        self.auto_every = tk.IntVar(value=5)
        self._auto_job = None
        self._auto_next = "safety"
        self.last_layers = None
        self.metric_details = {}
        self.metric_provenance = {}
        self.metric_notes = {
            "delay_ms": "One-way Rover bundle submission → complete Earth bundle reception; synchronized clocks required.",
            "throughput_kbps": "Define the measurement interval and whether counting TCP/IP bytes, BPv7 bytes or useful JSON bits.",
            "overhead_b": "Actual added bytes for the selected exchange and hop; packet capture required.",
            "storage_wait_ms": "Satellite complete bundle reception → outgoing forward timestamp; requires Satellite instrumentation.",
            "delivery_pct": "Earth received application requests / Rover submitted application requests over a settled run; replies are not enough."
        }

        self._build(banner)
        self._bind_keys()
        self.after(50, self._poll)
        self.after(30, self._animate)
        self.after(200, self._clock)

    # ---------------------------------------------------------------- fonts
    def _fonts(self):
        fams = set(tkfont.families(self))
        sans = next((f for f in ("Ubuntu", "Inter", "Noto Sans", "DejaVu Sans", "Helvetica") if f in fams), "TkDefaultFont")
        mono = next((f for f in ("Ubuntu Mono", "JetBrains Mono", "DejaVu Sans Mono", "Courier") if f in fams), "TkFixedFont")
        self.F = dict(
            title=(sans, 13 if self.compact else 17, "bold"),
            h2=(sans, 9 if self.compact else 11, "bold"),
            body=(sans, 8 if self.compact else 10), body_b=(sans, 8 if self.compact else 10, "bold"),
            small=(sans, 8 if self.compact else 9), small_b=(sans, 8 if self.compact else 9, "bold"),
            tiny_b=(sans, 7 if self.compact else 8, "bold"),
            metric=(sans, 17 if self.compact else 24, "bold"),
            mono=(mono, 8 if self.compact else 10), mono_s=(mono, 8 if self.compact else 9),
            card=(sans, 10 if self.compact else 13, "bold"),
        )
        self._mono_font = tkfont.Font(self, font=self.F["mono_s"])
        self._small_font = tkfont.Font(self, font=self.F["small"])

    # ---------------------------------------------------------------- layout
    def _panel(self, parent, title, right=None):
        f = tk.Frame(parent, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"])
        hdr = tk.Frame(f, bg=T["panel"])
        hdr.pack(fill="x", padx=9 if self.compact else 14,
                 pady=(5, 3) if self.compact else (10, 6))
        tk.Label(hdr, text=title, bg=T["panel"], fg=T["text"], font=self.F["h2"]).pack(side="left")
        f.hdr = hdr
        return f

    def _build(self, banner):
        gap = 4 if self.compact else 10
        root = tk.Frame(self, bg=T["bg"])
        root.pack(fill="both", expand=True, padx=6 if self.compact else 14,
                  pady=4 if self.compact else 12)
        root.columnconfigure(0, weight=1)
        if banner:
            self._banner(root, banner)
        self._header(root)

        mid = tk.Frame(root, bg=T["bg"])
        mid.pack(fill="x", pady=(gap, 0))
        mid.columnconfigure(0, weight=11)
        mid.columnconfigure(1, weight=9, minsize=350 if self.compact else 400)
        self._topology(mid).grid(row=0, column=0, sticky="nsew", padx=(0, 5 if self.compact else 10))
        self._app_cards(mid).grid(row=0, column=1, sticky="nsew")

        self._metrics(root).pack(fill="x", pady=(gap, 0))

        self._statusbar(root)   # packed before the bottom row so it is never squeezed out

        bot = tk.Frame(root, bg=T["bg"])
        bot.pack(fill="both", expand=True, pady=(gap, 0))
        bot.columnconfigure(0, weight=9, uniform="b")
        bot.columnconfigure(1, weight=11, uniform="b")
        bot.rowconfigure(0, weight=1)
        self._exchange(bot).grid(row=0, column=0, sticky="nsew", padx=(0, 5 if self.compact else 10))
        self._log(bot).grid(row=0, column=1, sticky="nsew")

    def _banner(self, root, path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            W = self.winfo_screenwidth()
            h = 90
            r = W / img.width
            img = img.resize((W, int(img.height * r)))
            top = max(0, (img.height - h) // 2)
            self._banner_img = ImageTk.PhotoImage(img.crop((0, top, W, top + h)))
            tk.Label(root, image=self._banner_img, bg=T["bg"], bd=0, anchor="center").pack(fill="x", pady=(0, 8))
        except Exception as e:  # Pillow missing or bad file: skip silently
            print("banner skipped:", e)

    def _header(self, root):
        h = tk.Frame(root, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"])
        h.pack(fill="x")
        stripe = tk.Frame(h, bg=T["orange"], width=5)
        stripe.pack(side="left", fill="y")
        left = tk.Frame(h, bg=T["panel"])
        left.pack(side="left", padx=8 if self.compact else 16,
                  pady=5 if self.compact else 10)
        trow = tk.Frame(left, bg=T["panel"])
        trow.pack(anchor="w")
        tk.Label(trow, text="MARS ROVER MISSION CONTROL", bg=T["panel"], fg=T["text"], font=self.F["title"]).pack(side="left")
        if self.event:
            tk.Label(trow, text=self.event.upper(), bg=T["orange_dk"], fg="#ffffff", font=self.F["tiny_b"],
                     padx=5 if self.compact else 8, pady=1 if self.compact else 2).pack(
                         side="left", padx=(6 if self.compact else 12, 0))
        tk.Label(left, text="CoAP over BPv7  ·  draft-ietf-core-coap-bp-05  ·  IPN dual-application experiment",
                 bg=T["panel"], fg=T["muted"], font=self.F["body"]).pack(anchor="w")

        right = tk.Frame(h, bg=T["panel"])
        right.pack(side="right", padx=6 if self.compact else 16)
        self.clock = tk.Label(right, text="", bg=T["panel"], fg=T["text"], font=self.F["mono"])
        self.clock.pack(side="right", padx=(6 if self.compact else 14, 0))
        self._kv(right, "LAST UPDATE", "--:--:--", "last_upd")
        self._kv(right, "RUN", f"SOL {self.sol}", "run_lbl")
        self._kv(right, "MODE", self.mode, "mode_lbl")
        self.live_pill = tk.Label(right, text=("●  PREVIEW ONLY" if self.mode == "PREVIEW" else "●  CONNECTING"), bg=T["panel2"], fg=T["warn"],
                                  font=self.F["small_b"], padx=6 if self.compact else 10,
                                  pady=2 if self.compact else 4)
        self.live_pill.pack(side="right", padx=(0, 5 if self.compact else 14))

    def _kv(self, parent, k, v, attr):
        f = tk.Frame(parent, bg=T["panel"])
        f.pack(side="right", padx=5 if self.compact else 10)
        tk.Label(f, text=k, bg=T["panel"], fg=T["faint"], font=self.F["tiny_b"]).pack(anchor="e")
        lbl = tk.Label(f, text=v, bg=T["panel"], fg=T["text"], font=self.F["body_b"])
        lbl.pack(anchor="e")
        setattr(self, attr, lbl)

    # ---------------------------------------------------------------- topology
    def _topology(self, parent):
        p = self._panel(parent, "DTN PATH  ·  STORE-AND-FORWARD")
        legend = tk.Frame(p.hdr, bg=T["panel"])
        legend.pack(side="right")
        for txt, col in (("Safety", T["teal"]), ("Science", T["orange"])):
            tk.Label(legend, text="■", bg=T["panel"], fg=col, font=self.F["small"]).pack(side="left")
            tk.Label(legend, text=txt + "   ", bg=T["panel"], fg=T["muted"], font=self.F["small"]).pack(side="left")
        if not self.narrow:
            tk.Label(legend, text="REQ above link · RSP below", bg=T["panel"], fg=T["faint"], font=self.F["small"]).pack(side="left")
        if self.on_toggle_link:
            FlatButton(legend, "Toggle link [L]" if self.narrow else "Cut / restore Sat-Earth link  [L]",
                       lambda: self.on_toggle_link("sat-earth"),
                       bg=T["panel2"], hover=T["border"], fg=T["text"], font=self.F["small_b"], padx=10, pady=3
                       ).pack(side="left", padx=(10, 0))
        self.topo = tk.Canvas(p, height=124 if self.compact else 250,
                              bg=T["panel"], highlightthickness=0)
        self.topo.pack(fill="both", expand=True,
                       padx=5 if self.compact else 8,
                       pady=(0, 4 if self.compact else 8))
        self.topo.bind("<Configure>", lambda e: self._draw_topology())
        return p

    def _geom(self):
        """Node layout. Tall canvas: icon on top of the text. Short canvas: icon left of the text."""
        c = self.topo
        W, H = max(c.winfo_width(), 1), max(c.winfo_height(), 110)
        vertical = H >= 190
        if vertical:
            bw = min(230, W * 0.24)
            ih = max(40, min(80, H - 130))
            bh = min(H - 12, ih + 112)
        else:
            bw = min(230, W * 0.25)
            bh = min(132, H - 16)
            ih = max(30, min(58, bh - 30, bw * 0.32))
        cy = H / 2
        xs = {"rover": 10 + bw / 2, "sat": W / 2, "earth": W - 10 - bw / 2}
        self._lay = dict(vertical=vertical, ih=ih)
        return W, H, bw, bh, cy, xs

    def _node_layout(self, n, xs, bw, bh, cy):
        """Positions inside one node box: icon centre, text column centre/width, text rows."""
        x = xs[n]
        x1, y1 = x - bw / 2, cy - bh / 2
        ih = self._lay["ih"]
        if self._lay["vertical"]:
            ty = y1 + ih + 18
            return dict(icon=(x, y1 + 8 + ih / 2), tx=x, tw=bw - 16,
                        title=ty, eid=ty + 17, chips=ty + 41, sub=ty + 35, slots=ty + 57, store=ty + 78)
        tx0 = x1 + ih + 12
        tw = x + bw / 2 - tx0 - 4
        return dict(icon=(x1 + 8 + ih / 2, cy), tx=tx0 + tw / 2, tw=tw,
                    title=y1 + 16, eid=y1 + 32, chips=y1 + 54, sub=y1 + 49, slots=y1 + 70, store=y1 + bh - 12)

    def _store_slot(self, k, xs, bw, bh, cy):
        L = self._node_layout("sat", xs, bw, bh, cy)
        per_row = max(1, int(L["tw"] // 38))
        row, col = divmod(k, per_row)
        n_in_row = per_row
        x0 = L["tx"] - (n_in_row - 1) * 38 / 2
        return x0 + col * 38, L["slots"] - row * 20

    def _draw_topology(self):
        c = self.topo
        c.delete("static")
        W, H, bw, bh, cy, xs = self._geom()
        # planets as faint horizon arcs
        c.create_oval(-W * 0.25, H * 0.62, W * 0.42, H * 2.2, fill=T["mars"], outline="", tags="static")
        c.create_oval(W * 0.58, H * 0.62, W * 1.25, H * 2.2, fill=T["earth"], outline="", tags="static")
        random.seed(7)
        for _ in range(70):
            x, y = random.uniform(0, W), random.uniform(0, H * 0.6)
            r = random.choice((0.7, 0.7, 1.0, 1.4))
            c.create_oval(x - r, y - r, x + r, y + r, fill=random.choice(("#33415f", "#46557a", "#5d6c92")),
                          outline="", tags="static")
        random.seed()
        # links
        for lid, a, b in (("rover-sat", "rover", "sat"), ("sat-earth", "sat", "earth")):
            x1, x2 = xs[a] + bw / 2, xs[b] - bw / 2
            up = self.links[lid]
            col = T["faint"] if up is None else (T["link"] if up else T["bad"])
            c.create_line(x1, cy, x2, cy, fill=col, width=3, dash=() if up else (6, 5),
                          tags=("static", f"link-{lid}"))
            c.create_line(x1, cy, x2, cy, fill="", width=18, tags=("static", f"link-{lid}"))  # click target
            mx = (x1 + x2) / 2
            roomy = (x2 - x1) > 110
            c.create_text(mx, cy - 32, text="TCPCLv3" if roomy else "TCPCLv3", fill=T["faint"],
                          font=self.F["tiny_b"], tags="static")
            c.create_text(mx, cy + 32, text=("UNVERIFIED" if up is None else ("LINK UP" if up else "NO CONTACT")) if roomy else ("?" if up is None else ("UP" if up else "DOWN")),
                          fill=T["faint"] if up is None else (T["ok"] if up else T["bad"]), font=self.F["tiny_b"], tags="static")
            if self.on_toggle_link:
                c.tag_bind(f"link-{lid}", "<Button-1>", lambda e, l=lid: self.on_toggle_link(l))
                c.tag_bind(f"link-{lid}", "<Enter>", lambda e: c.config(cursor="hand2"))
                c.tag_bind(f"link-{lid}", "<Leave>", lambda e: c.config(cursor=""))
        # nodes
        vertical = self._lay["vertical"]
        ih = self._lay["ih"]
        for n, (name, eid) in NODES.items():
            x = xs[n]
            x1, y1, x2, y2 = x - bw / 2, cy - bh / 2, x + bw / 2, cy + bh / 2
            round_rect(c, x1, y1, x2, y2, r=14, fill=T["panel2"], outline=T["border"], width=2,
                       tags=("static", f"node-{n}"))
            L = self._node_layout(n, xs, bw, bh, cy)
            self._node_icon(c, n, L["icon"][0], L["icon"][1], ih)
            tx, tw = L["tx"], L["tw"]
            c.create_text(tx, L["title"], text=name, fill=T["text"], font=self.F["h2"], tags="static")
            c.create_text(tx, L["eid"], text=eid, fill=T["muted"], font=self.F["mono_s"], tags="static")
            if n == "rover":
                self._chips(c, tx, L["chips"], tw, [
                    (("ipn:0.1.10  safety", "ipn:0.1.10", ".10"), "safety"),
                    (("ipn:0.1.11  science", "ipn:0.1.11", ".11"), "science")])
            elif n == "earth":
                self._chips(c, tx, L["chips"], tw, [
                    (("/mission/safety-guidance", "/safety", "/s"), "safety"),
                    (("/science/observations", "/science", "/sci"), "science")], always=True)
            else:
                sub = next((s for s in ("uD3TN relay  ·  no CoAP layer", "uD3TN relay  ·  no CoAP", "uD3TN relay")
                            if self._small_font.measure(s) <= tw), "relay")
                c.create_text(tx, L["sub"], text=sub, fill=T["faint"], font=self.F["small"], tags="static")
                c.create_text(tx, L["store"], text="", fill=T["muted"], font=self.F["small_b"],
                              tags=("static", "storage"))
        self._storage_short = not vertical
        self._update_storage()

    def _chips(self, c, x, y, maxw, items, always=False):
        for i, (labels, app) in enumerate(items):
            label = next((l for l in labels if self._mono_font.measure(l) + 14 <= maxw), labels[-1])
            on = always or self.registered[app]
            col = APPS[app]["color"] if on else T["faint"]
            yy = y + i * 22
            w = 14 + self._mono_font.measure(label)
            round_rect(c, x - w / 2, yy - 9, x + w / 2, yy + 9, r=8, fill=T["panel"], outline=col, width=1, tags="static")
            c.create_text(x, yy, text=label, fill=col, font=self.F["mono_s"], tags="static")

    # ---------------------------------------------------------------- node artwork
    def _node_icon(self, c, n, cx, cy, size):
        img = self._user_image(n, int(size))
        if img is not None:
            c.create_image(cx, cy, image=img, tags="static")
        else:
            {"rover": draw_rover, "sat": draw_satellite, "earth": draw_earth}[n](c, cx, cy, size, "static")

    def _user_image(self, n, size):
        """Optional photo override: images/rover.png, images/satellite.png, images/earth.png."""
        key = (n, size)
        if key in self._img_cache:
            return self._img_cache[key]
        img = None
        stem = {"rover": "rover", "sat": "satellite", "earth": "earth"}[n]
        for ext in (".png", ".gif", ".jpg", ".jpeg"):
            path = os.path.join(self.images_dir, stem + ext)
            if not os.path.isfile(path):
                continue
            try:
                from PIL import Image, ImageTk
                im = Image.open(path).convert("RGBA")
                im.thumbnail((size, size), Image.LANCZOS)
                img = ImageTk.PhotoImage(im)
            except ImportError:
                if ext in (".png", ".gif"):
                    try:
                        raw = tk.PhotoImage(file=path)
                        f = max(1, math.ceil(max(raw.width(), raw.height()) / size))
                        img = raw.subsample(f, f)
                    except tk.TclError:
                        img = None
            except Exception:
                img = None
            if img is not None:
                break
        self._img_cache[key] = img
        return img


    def _update_storage(self):
        held = [t for t in self.tokens if t["phase"] == "hold" and t["path"][t["i"]] == "sat"]
        c = self.topo
        if getattr(self, "_storage_short", False):
            txt = f"STORED: {len(held)}" if held else "empty"
        else:
            txt = f"STORAGE: {len(held)} bundle{'s' if len(held) != 1 else ''}" if held else "storage empty"
        c.itemconfig("storage", text=txt, fill=T["warn"] if held else T["faint"])
        c.itemconfig("node-sat", outline=T["warn"] if held else T["border"])

    def _spawn(self, app, kind):
        path = ["rover", "sat", "earth"] if kind == "REQ" else ["earth", "sat", "rover"]
        tok = dict(app=app, kind=kind, path=path, i=0, phase="hold", t0=time.time(), then=None, min_hold=0)
        self.tokens.append(tok)
        return tok

    def _link_between(self, a, b):
        return "rover-sat" if {a, b} == {"rover", "sat"} else "sat-earth"

    def _animate(self):
        now = time.time()
        c = self.topo
        c.delete("token")
        if c.winfo_width() > 10:
            W, H, bw, bh, cy, xs = self._geom()
            for tok in list(self.tokens):
                el = (now - tok["t0"]) * 1000
                p = tok["path"]
                if tok["phase"] == "hold":
                    nxt = p[tok["i"] + 1]
                    if el >= tok["min_hold"] and self.links[self._link_between(p[tok["i"]], nxt)]:
                        tok["phase"], tok["t0"] = "move", now
                elif tok["phase"] == "move" and el >= MOVE_MS:
                    tok["i"] += 1
                    if tok["i"] == len(p) - 1:
                        self.tokens.remove(tok)
                        self.flash[p[-1]] = (APPS[tok["app"]]["color"], now + 0.6)
                        if tok["then"]:
                            tok["then"]()
                        continue
                    tok["phase"], tok["t0"], tok["min_hold"] = "hold", now, HOLD_MS
                # draw
                dy = -11 if tok["kind"] == "REQ" else 11
                a = p[tok["i"]]
                if tok["phase"] == "move":
                    b = p[tok["i"] + 1]
                    sgn = 1 if xs[b] > xs[a] else -1
                    xa, xb = xs[a] + sgn * bw / 2, xs[b] - sgn * bw / 2
                    f = min(1.0, (now - tok["t0"]) * 1000 / MOVE_MS)
                    f = 0.5 - math.cos(math.pi * f) / 2
                    x, y = xa + (xb - xa) * f, cy + dy
                else:
                    held = [t for t in self.tokens if t["phase"] == "hold" and t["path"][t["i"]] == a]
                    k = held.index(tok)
                    if a == "sat":
                        x, y = self._store_slot(k, xs, bw, bh, cy)
                    else:
                        sgn = 1 if a == "rover" else -1
                        x, y = xs[a] + sgn * (bw / 2 + 22 + k * 4), cy + dy
                self._draw_token(x, y, tok)
            self._update_storage()
            # node flashes
            for n in NODES:
                col, until = self.flash.get(n, (None, 0))
                if n != "sat":
                    c.itemconfig(f"node-{n}", outline=col if now < until else T["border"])
        self.after(30, self._animate)

    def _draw_token(self, x, y, tok):
        c = self.topo
        col = APPS[tok["app"]]["color"]
        round_rect(c, x - 17, y - 8, x + 17, y + 8, r=7, fill=col if tok["kind"] == "REQ" else T["panel"],
                   outline=col, width=2, tags="token")
        c.create_text(x, y, text=tok["kind"], fill="#0a101d" if tok["kind"] == "REQ" else col,
                      font=self.F["tiny_b"], tags="token")

    # ---------------------------------------------------------------- app cards
    def _app_cards(self, parent):
        p = self._panel(parent, "APPLICATIONS")
        self.cards = {}
        for app, a in APPS.items():
            card = tk.Frame(p, bg=T["panel2"], highlightthickness=1, highlightbackground=T["border"])
            card.pack(fill="x", padx=6 if self.compact else 12,
                      pady=(0, 4 if self.compact else 8))
            tk.Frame(card, bg=a["color"], width=5).pack(side="left", fill="y")
            body = tk.Frame(card, bg=T["panel2"])
            body.pack(side="left", fill="both", expand=True,
                      padx=6 if self.compact else 12,
                      pady=3 if self.compact else 8)
            r1 = tk.Frame(body, bg=T["panel2"])
            r1.pack(fill="x")
            tk.Label(r1, text=a["name"], bg=T["panel2"], fg=a["color"], font=self.F["card"]).pack(side="left")
            reg = tk.Label(r1, text="● registering", bg=T["panel2"], fg=T["warn"], font=self.F["small_b"])
            reg.pack(side="left", padx=5 if self.compact else 10)
            btn = FlatButton(r1, f"Send {a['method']}  [{a['key']}]", lambda x=app: self._send(x),
                             bg=a["dark"], hover=a["color"], font=self.F["body_b"])
            btn.pack(side="right")
            uri = (f"{a['method']} {a['path']}  ·  {a['eid']} → {EARTH_EID}  ·  NON" if self.narrow else
                   f"{a['method']} coap://{COAP_URI_AUTHORITY}{a['path']}   ·   from {a['eid']}   ·   NON")
            if not self.short:
                tk.Label(body, text=uri, bg=T["panel2"], fg=T["muted"], font=self.F["mono_s"]
                         ).pack(anchor="w", pady=(3, 4))
            else:
                tk.Frame(body, bg=T["panel2"], height=2).pack()
            stats = tk.Label(body, text="Last: -    RTT: -    Matched replies: 0 / 0", bg=T["panel2"], fg=T["text"],
                             font=self.F["body"])
            stats.pack(anchor="w")
            self.cards[app] = dict(reg=reg, stats=stats, btn=btn)

        if self.mode != "DEMO":
            return p
        if self.short:
            auto = tk.Frame(p.hdr, bg=T["panel"])
            auto.pack(side="right")
        else:
            auto = tk.Frame(p, bg=T["panel"])
            auto.pack(fill="x", padx=12, pady=(0, 10))
        tk.Checkbutton(auto, text="Auto every" if self.short else "Auto-run both apps, every", variable=self.auto_var, command=self._auto_toggle,
                       bg=T["panel"], fg=T["text"], selectcolor=T["panel2"], activebackground=T["panel"],
                       activeforeground=T["text"], highlightthickness=0, font=self.F["body"]).pack(side="left")
        tk.Spinbox(auto, from_=2, to=120, width=4, textvariable=self.auto_every, bg=T["panel2"], fg=T["text"],
                   buttonbackground=T["panel2"], insertbackground=T["text"], relief="flat",
                   highlightthickness=0, font=self.F["body"]).pack(side="left", padx=4)
        tk.Label(auto, text="s", bg=T["panel"], fg=T["text"], font=self.F["body"]).pack(side="left")
        return p

    def _refresh_card(self, app):
        s = self.app_stats[app]
        rtt = f"{s['rtt']:.0f} ms" if s["rtt"] is not None else "-"
        self.cards[app]["stats"].config(text=f"Last: {s['code']}    RTT: {rtt}    Matched replies: {s['delivered']} / {s['sent']}")

    def _send(self, app):
        if not self.registered[app]:
            self._add_log("ERROR", f"{app}: endpoint not registered yet")
            return
        if self.on_send:
            self.on_send(app)

    def _auto_toggle(self):
        if self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None
        if self.auto_var.get():
            self._auto_tick()

    def _auto_tick(self):
        self._send(self._auto_next)
        self._auto_next = "science" if self._auto_next == "safety" else "safety"
        try:
            ms = max(2, int(self.auto_every.get())) * 500   # alternate apps -> each app every N s
        except (tk.TclError, ValueError):
            ms = 2500
        self._auto_job = self.after(ms, self._auto_tick)

    # ---------------------------------------------------------------- metrics
    def _metrics(self, root):
        p = self._panel(root, "CURRENT RUN MEASUREMENTS")
        self.metric_app_lbl = tk.Label(p.hdr, text="waiting for first exchange", bg=T["panel"], fg=T["muted"],
                                       font=self.F["small"])
        self.metric_app_lbl.pack(side="left", padx=12)
        self.live_rtt_lbl = tk.Label(p.hdr, text="Application RTT: N/A", bg=T["panel"],
                                     fg=T["ok"], font=self.F["small"])
        self.live_rtt_lbl.pack(side="right", padx=8)
        row = tk.Frame(p, bg=T["panel"])
        row.pack(fill="x", padx=6 if self.compact else 12,
                 pady=(0, 5 if self.compact else 12))
        spec = [
            ("delay_ms", "End-to-end delay", "ms", "Rover submit → Earth receive", lambda v: f"{v:.0f}", True),
            ("throughput_kbps", "Throughput", "kbps", "Sat→Earth TCPCL / fixed window", lambda v: f"{v:.2f}", False),
            ("overhead_b", "Protocol overhead", "B", "Ethernet data frames − BPv7 payload", lambda v: f"{v:.0f}", True),
            ("storage_wait_ms", "Storage wait", "ms", "Satellite received → forwarded", lambda v: f"{v:.0f}", True),
            ("delivery_pct", "Delivery ratio", "%", "Earth received / submitted", lambda v: f"{v:.0f}", False),
        ]
        self.tiles = {}
        for i, (k, title, unit, sub, fmt, lib) in enumerate(spec):
            t = MetricTile(row, self.F, k, title, unit, sub, fmt, lower_is_better=lib)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else (4 if self.compact else 8), 0))
            row.columnconfigure(i, weight=1, uniform="m")
            self.tiles[k] = t
            t.update_value(None, APPS["science"]["color"],
                           subtitle="Awaiting verified measurement")
            def bind_metric_click(widget, metric=k):
                widget.bind("<Button-1>", lambda _e, key=metric: self._metric_popup(key))
                widget.configure(cursor="hand2")
                for child in widget.winfo_children():
                    bind_metric_click(child, metric)
            bind_metric_click(t)
        return p

    def _metric_popup(self, key):
        title_map = {"delay_ms": "One-way end-to-end delay", "throughput_kbps": "Throughput",
                     "overhead_b": "Protocol overhead", "storage_wait_ms": "Satellite storage wait",
                     "delivery_pct": "Delivery ratio"}
        win = tk.Toplevel(self)
        win.title(title_map.get(key, key) + " — Evidence and calculation")
        win.configure(bg=T["bg"])
        win.geometry("700x410")
        tk.Label(win, text=title_map.get(key, key), bg=T["bg"], fg=T["text"],
                 font=self.F["h2"]).pack(anchor="w", padx=18, pady=(15, 5))
        info = dict(metric=key, definition=self.metric_notes.get(key),
                    source=self.metric_provenance.get(key, "NOT YET MEASURED"),
                    evidence=self.metric_details.get(key, {}))
        box = tk.Text(win, bg=T["panel"], fg=T["text"], wrap="word", font=self.F["mono_s"],
                      padx=12, pady=10, highlightthickness=0)
        box.pack(fill="both", expand=True, padx=18, pady=8)
        box.insert("1.0", json.dumps(info, indent=2, ensure_ascii=False, default=str))
        box.config(state="disabled")
        FlatButton(win, "Close", win.destroy, bg=T["panel2"], fg=T["text"],
                   font=self.F["body_b"]).pack(pady=(0, 15))

    # ---------------------------------------------------------------- exchange
    def _exchange(self, parent):
        p = self._panel(parent, "LAST EXCHANGE")
        tabs = tk.Frame(p.hdr, bg=T["panel"])
        tabs.pack(side="left", padx=12)
        self.tab_btns = {}
        for app, a in APPS.items():
            b = FlatButton(tabs, a["name"].split()[-1].title(), lambda x=app: self._show_exchange(x),
                           bg=T["panel2"], hover=T["border"], font=self.F["small_b"], padx=10, pady=2)
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[app] = b
        if not self.narrow:
            tk.Label(p.hdr, text="simulated data  ·  demo backend" if self.mode == "DEMO"
                     else ("real BPv7 transmission" if self.mode == "LIVE" else "layout preview — no network"),
                     bg=T["panel"], fg=T["faint"], font=self.F["small"]).pack(side="right")

        grid = tk.Frame(p, bg=T["panel"])
        grid.pack(fill="both", expand=True, padx=7 if self.compact else 12)
        grid.columnconfigure(0, weight=1, uniform="x")
        grid.columnconfigure(1, weight=1, uniform="x")
        grid.rowconfigure(1, weight=1)
        self.req_title = tk.Label(grid, text="SENT FROM ROVER", bg=T["panel"], fg=T["muted"], font=self.F["small_b"], anchor="w")
        self.req_title.grid(row=0, column=0, sticky="ew")
        self.rsp_title = tk.Label(grid, text="RESPONSE FROM EARTH", bg=T["panel"], fg=T["muted"], font=self.F["small_b"], anchor="w")
        self.rsp_title.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.req_txt = self._textbox(grid)
        self.req_txt.grid(row=1, column=0, sticky="nsew", pady=(3, 0))
        self.rsp_txt = self._textbox(grid)
        self.rsp_txt.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(3, 0))

        ovf = tk.Frame(p, bg=T["panel"])
        if not self.short:   # on small screens the total is in the Protocol overhead tile
            ovf.pack(fill="x", padx=12, pady=(0, 8), before=grid, side="bottom")
        else:
            tk.Frame(p, bg=T["panel"], height=4).pack(before=grid, side="bottom")
        tk.Label(ovf, text="OVERHEAD BREAKDOWN  (bytes per bundle, last exchange)", bg=T["panel"], fg=T["muted"],
                 font=self.F["small_b"], anchor="w").pack(fill="x", pady=(6, 2))
        self.ovh = tk.Canvas(ovf, height=40 if self.short else 46, bg=T["panel"], highlightthickness=0)
        self.ovh.pack(fill="x")
        self.ovh.bind("<Configure>", lambda e: self._draw_overhead())
        self._show_exchange("science")
        return p

    def _textbox(self, parent):
        t = tk.Text(parent, height=3 if self.short else 6, bg=T["bg"], fg=T["text"], font=self.F["mono"], relief="flat", wrap="word",
                    highlightthickness=1, highlightbackground=T["border"],
                    padx=5 if self.compact else 10, pady=3 if self.compact else 8,
                    insertbackground=T["text"])
        for k, col in (("k", T["muted"]), ("ok", T["ok"]), ("bad", T["bad"]), ("teal", T["teal"]),
                       ("orange", T["orange"]), ("faint", T["faint"]), ("bp", T["bp"])):
            t.tag_configure(k, foreground=col)
        t.configure(state="disabled")
        return t

    def _fill(self, t, parts):
        t.configure(state="normal")
        t.delete("1.0", "end")
        for text, tag in parts:
            t.insert("end", text, tag)
        t.configure(state="disabled")

    def _show_exchange(self, app):
        self.view_app.set(app)
        for a, b in self.tab_btns.items():
            b.set_colors(APPS[a]["dark"] if a == app else T["panel2"], APPS[a]["color"] if a == app else T["border"])
        ex = self.exchanges[app]
        ctag = "teal" if app == "safety" else "orange"
        rq, rs = ex["req"], ex["resp"]
        if rq:
            parts = [(f"{rq['msg_type']} {rq['method']} ", ctag), (rq["uri"] + "\n", None),
                     ("payload  ", "k"), (self._fmt_payload(rq.get("payload")) + "\n", None),
                     (APPS[app]["eid"] + " → " + EARTH_EID, None)]
            if rq.get("mid") is not None:
                parts += [("  MID ", "k"), (f"0x{rq['mid']:06X}", None)]
            if rq.get("token") is not None:
                parts += [("  Tkn ", "k"), (f"{rq['token']:04x}" if isinstance(rq["token"], int) else str(rq["token"]), None)]
            parts += [("\n", None),
                      ("submitted to local µD3TN at " + datetime.fromtimestamp(rq["submit_ts"]).strftime("%H:%M:%S.%f")[:-3]
                       if rq.get("submit_ts") else "queued locally at " + datetime.fromtimestamp(rq["ts"]).strftime("%H:%M:%S.%f")[:-3], "faint")]
        else:
            parts = [("No request sent yet.\nPress the Send button or key " + APPS[app]["key"] + ".", "faint")]
        self._fill(self.req_txt, parts)
        if rs:
            good = rs["code"].startswith("2.")
            parts = [(rs["code"] + "\n", "ok" if good else "bad")]
            if rs.get("location"):
                parts += [("Location  ", "k"), (rs["location"] + "\n", None)]
            parts += [("payload  ", "k"), (self._fmt_payload(rs.get("payload")) + "\n", None)]
            if rs.get("rtt_ms") is not None:
                parts += [("RTT (application)  ", "k"), (f"{rs['rtt_ms']:.0f} ms", None),
                          ("   request submit → response receive", "faint")]
        elif rq:
            parts = [("awaiting response… (bundle in transit)", "faint")]
        else:
            parts = [("-", "faint")]
        self._fill(self.rsp_txt, parts)

    @staticmethod
    def _fmt_payload(p):
        if p is None:
            return "(empty)"
        if isinstance(p, (dict, list)):
            return json.dumps(p, separators=(", ", ": "))
        if isinstance(p, bytes):
            try:
                return p.decode()
            except UnicodeDecodeError:
                return p.hex()
        return str(p)

    def _draw_overhead(self):
        c = self.ovh
        c.delete("all")
        w = c.winfo_width()
        L = self.last_layers
        if not L or w < 50:
            c.create_text(4, 18, text="appears after the first exchange", anchor="w", fill=T["faint"], font=self.F["small"])
            return
        total = sum(L.values()) or 1
        x = 0
        for name, v in L.items():
            seg = (w - 2) * v / total
            col = LAYER_COLORS.get(name, T["muted"])
            c.create_rectangle(x, 2, x + seg - 2, 20, fill=col, outline="")
            if seg > 34:
                c.create_text(x + seg / 2, 11, text=str(v), fill="#0a101d", font=self.F["tiny_b"])
            c.create_text(x + 2, 33, text=name, anchor="w", fill=col, font=self.F["tiny_b"]) if seg > 40 else None
            x += seg

    # ---------------------------------------------------------------- log
    def _log(self, parent):
        p = self._panel(parent, "LIVE BPv7 / CoAP EVENT LOG")
        FlatButton(p.hdr, "Export", self._export_log, bg=T["panel2"], hover=T["border"], fg=T["text"],
                   font=self.F["small_b"], padx=10, pady=2).pack(side="right")
        FlatButton(p.hdr, "Clear", self._clear_log, bg=T["panel2"], hover=T["border"], fg=T["text"],
                   font=self.F["small_b"], padx=10, pady=2).pack(side="right", padx=4)
        flt = tk.Frame(p, bg=T["panel"])
        flt.pack(fill="x", padx=7 if self.compact else 12,
                 pady=(0, 2 if self.compact else 4))
        for k, col in LOG_COLORS.items():
            tk.Checkbutton(flt, text=k, variable=self.log_filter[k], command=self._rerender_log, bg=T["panel"],
                           fg=col, selectcolor=T["panel2"], activebackground=T["panel"], activeforeground=col,
                           highlightthickness=0, font=self.F["tiny_b"]).pack(side="left", padx=(0, 4))
        box = tk.Frame(p, bg=T["panel"])
        box.pack(fill="both", expand=True, padx=7 if self.compact else 12,
                 pady=(0, 5 if self.compact else 12))
        self.log_txt = tk.Text(box, height=4 if self.short else 8, bg=T["bg"], fg=T["text"], font=self.F["mono_s"], relief="flat",
                               wrap="word", highlightthickness=1, highlightbackground=T["border"],
                               padx=5 if self.compact else 8, pady=3 if self.compact else 6)
        sb = tk.Scrollbar(box, command=self.log_txt.yview, bg=T["panel2"], troughcolor=T["bg"],
                          activebackground=T["border"], highlightthickness=0, bd=0, width=10)
        self.log_txt.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self.log_txt.pack(side="left", fill="both", expand=True)
        self.log_txt.tag_configure("ts", foreground=T["faint"])
        indent = self._mono_font.measure("13:36:38.960  METRICS ")
        self.log_txt.tag_configure("row", lmargin2=indent)
        for k, col in LOG_COLORS.items():
            self.log_txt.tag_configure(k, foreground=col)
        self.log_txt.tag_configure("ERRLINE", background="#2a1316")
        return p

    def _add_log(self, cat, msg, ts=None):
        cat = cat if cat in LOG_COLORS else "INFO"
        row = (ts or time.time(), cat, msg)
        self.log_rows.append(row)
        if self.log_filter[cat].get():
            self._write_log_row(row)

    def _write_log_row(self, row):
        ts, cat, msg = row
        t = self.log_txt
        at_end = t.yview()[1] > 0.98
        t.configure(state="normal")
        t.insert("end", datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3] + "  ", ("ts", "row"))
        t.insert("end", f"{cat:<8}", (cat, "row"))
        t.insert("end", msg + "\n", ("ERRLINE", "row") if cat == "ERROR" else ("row",))
        if int(t.index("end-1c").split(".")[0]) > 3000:
            t.delete("1.0", "500.0")
        t.configure(state="disabled")
        if at_end:
            t.see("end")

    def _rerender_log(self):
        t = self.log_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")
        for row in self.log_rows[-2500:]:
            if self.log_filter[row[1]].get():
                self._write_log_row(row)
        t.see("end")

    def _clear_log(self):
        self.log_rows.clear()
        self._rerender_log()

    def _export_log(self):
        fn = filedialog.asksaveasfilename(defaultextension=".log", initialfile=f"sol{self.sol}_events.log")
        if fn:
            with open(fn, "w") as f:
                for ts, cat, msg in self.log_rows:
                    f.write(f"{datetime.fromtimestamp(ts).isoformat(timespec='milliseconds')}\t{cat}\t{msg}\n")
            self._add_log("INFO", f"log exported to {fn}")

    def _export_metrics(self):
        if not self.metric_rows:
            self._add_log("INFO", "no measurements to export yet")
            return
        fn = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"sol{self.sol}_metrics.csv")
        if fn:
            with open(fn, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(self.metric_rows[0].keys()))
                w.writeheader()
                w.writerows(self.metric_rows)
            self._add_log("INFO", f"{len(self.metric_rows)} measurement rows exported to {fn}")

    # ---------------------------------------------------------------- status bar
    def _statusbar(self, root):
        s = tk.Frame(root, bg=T["bg"])
        s.pack(side="bottom", fill="x", pady=(2 if self.compact else 6, 0))
        keys = "S send Safety   ·   C send Science   ·   F11 full screen"
        if self.on_toggle_link:
            keys += "   ·   L toggle Sat-Earth link" + ("" if self.narrow else "   ·   click a link to cut it")
        tk.Label(s, text=keys, bg=T["bg"], fg=T["faint"], font=self.F["small"]).pack(side="left")
        FlatButton(s, "Export measurements CSV", self._export_metrics, bg=T["panel2"], hover=T["border"],
                   fg=T["text"], font=self.F["small_b"], padx=10, pady=3).pack(side="right")
        self.runs_lbl = tk.Label(s, text="0 exchanges recorded", bg=T["bg"], fg=T["muted"], font=self.F["small"])
        self.runs_lbl.pack(side="right", padx=12)

    def _bind_keys(self):
        self.bind("<KeyPress-s>", lambda e: self._send("safety"))
        self.bind("<KeyPress-c>", lambda e: self._send("science"))
        if self.on_toggle_link:
            self.bind("<KeyPress-l>", lambda e: self.on_toggle_link("sat-earth"))
        self._fs = False

        def fs(e=None):
            self._fs = not self._fs
            self.attributes("-fullscreen", self._fs)
        self.bind("<F11>", fs)
        self.bind("<Escape>", lambda e: self._fs and fs())

    def _clock(self):
        self.clock.config(text=datetime.now().strftime("%a %d %b  %H:%M:%S"))
        self.after(1000, self._clock)

    # ---------------------------------------------------------------- event dispatch
    def _poll(self):
        for kind, ev in self.bridge.drain():
            try:
                getattr(self, "_on_" + kind)(ev)
            except Exception as e:  # never let a bad event kill the GUI
                self._add_log("ERROR", f"GUI could not handle {kind} event: {e}")
        self.after(50, self._poll)

    def _touch(self, ts):
        self.last_upd.config(text=datetime.fromtimestamp(ts).strftime("%H:%M:%S"))

    def _on_log(self, ev):
        self._add_log(ev["category"], ev["message"], ev["ts"])

    def _on_registered(self, ev):
        app = ev["app"]
        self.registered[app] = True
        self.cards[app]["reg"].config(text=f"● registered  {ev['eid']}", fg=T["ok"])
        self._draw_topology()
        if all(self.registered.values()):
            self.live_pill.config(text="●  " + ("AAP2 REGISTERED" if self.mode == "LIVE" else "DEMO RUNNING"), fg=T["ok"])
        self._touch(ev["ts"])

    def _on_link(self, ev):
        self.links[ev["link_id"]] = ev["up"]
        self._draw_topology()
        if all(self.registered.values()):
            if all(v is True for v in self.links.values()):
                self.live_pill.config(text="●  " + ("AAP2 REGISTERED" if self.mode == "LIVE" else "DEMO RUNNING"), fg=T["ok"])
            else:
                self.live_pill.config(text="●  DISRUPTED - bundles held", fg=T["warn"])

    def _on_request(self, ev):
        app = ev["app"]
        self.exchanges[app] = dict(req=ev, resp=None)
        self.app_stats[app]["sent"] += 1
        self._refresh_card(app)
        if self.mode == "DEMO":
            self._spawn(app, "REQ")
        self._show_exchange(app)
        self._touch(ev["ts"])

    def _on_submitted(self, ev):
        app = ev["app"]
        req = self.exchanges[app].get("req")
        if req is not None:
            req["submit_ts"] = ev["ts"]
            if ev.get("bundle_bytes") is not None:
                req["bp_payload_bytes"] = ev["bundle_bytes"]
        self._add_log("AAP2", f"{app}: BP payload {ev.get('bundle_bytes')} B submitted locally "
                      "(not yet proof of Earth delivery)")
        if self.view_app.get() == app:
            self._show_exchange(app)
        self._touch(ev["ts"])

    def _on_response(self, ev):
        app = ev["app"]
        self.exchanges[app]["resp"] = ev
        st = self.app_stats[app]
        st["code"], st["rtt"] = ev["code"], ev.get("rtt_ms")
        if self.mode == "LIVE" and ev.get("matched") and isinstance(ev.get("rtt_ms"), (int, float)):
            self.live_rtt_lbl.config(text=f"Application RTT: {ev['rtt_ms']:.1f} ms ({app})")
        if ev.get("matched") and str(ev["code"]).startswith("2."):
            st["delivered"] += 1
        self._refresh_card(app)
        # Visual travel is simulated; never imply measured hop timing in LIVE mode.
        if self.mode != "DEMO":
            if self.view_app.get() == app:
                self._show_exchange(app)
            self._touch(ev["ts"])
            return
        pending = next((t for t in self.tokens if t["app"] == app and t["kind"] == "REQ" and t["then"] is None), None)
        if pending:
            pending["then"] = lambda: self._spawn(app, "RSP")
        else:
            self._spawn(app, "RSP")
        if self.view_app.get() == app:
            self._show_exchange(app)
        self._touch(ev["ts"])

    def _on_metrics(self, ev):
        app = ev.get("app", "science")
        col = APPS.get(app, APPS["science"])["color"]
        src = ev.get("source") or "SOURCE UNSPECIFIED"
        d = ev.get("details") or {}
        fields = ("delay_ms", "throughput_kbps", "overhead_b", "storage_wait_ms")
        accepted_delay = None
        for key in fields:
            value = ev.get(key)
            if value is None:
                continue
            # One-way delay is not valid without independent clock/source evidence.
            if key == "delay_ms" and self.mode != "DEMO":
                if (not d.get("rover_submit_utc") or not d.get("earth_recv_utc") or
                    not d.get("clock_checked") or d.get("clock_stepped_during_run") is not False or
                    ev.get("clock_quality") is None):
                    self._add_log("ERROR", "One-way delay omitted: missing Rover/Earth timestamps")
                    continue
            self.tiles[key].update_value(value, col, provenance=src)
            if key == "delay_ms":
                accepted_delay = value
            self.metric_provenance[key] = src
            self.metric_details[key] = d
        count_good = ev.get("delivered") is not None and ev.get("sent") is not None
        if count_good and (self.mode == "DEMO" or ev.get("delivery_evidence") == "earth_receipt"):
            sent, received = ev["sent"], ev["delivered"]
            if sent > 0 and 0 <= received <= sent:
                pct = 100 * received / sent
                self.tiles["delivery_pct"].update_value(pct, col,
                    subtitle=f"{received} Earth-received / {sent} submitted ({app})", provenance=src)
                self.metric_provenance["delivery_pct"] = src
                self.metric_details["delivery_pct"] = d
        if ev.get("layers") and isinstance(ev["layers"], dict):
            L = ev["layers"]
            if all(isinstance(x, (int, float)) and x >= 0 for x in L.values()):
                self.last_layers = L
                self._draw_overhead()
        self.metric_app_lbl.config(text=f"last measurement: {APPS[app]['name'].title()}  ·  "
                                         f"{datetime.fromtimestamp(ev['ts']).strftime('%H:%M:%S')}  ·  {src}", fg=col)
        verified_ratio = (ev.get("delivery_evidence") == "earth_receipt" or self.mode == "DEMO")
        row = dict(time=datetime.fromtimestamp(ev["ts"]).isoformat(timespec="milliseconds"),
                   app=app, sol=self.sol, source=src,
                   delay_ms=accepted_delay if accepted_delay is not None else "",
                   throughput_kbps=ev.get("throughput_kbps") if ev.get("throughput_kbps") is not None else "",
                   overhead_b=ev.get("overhead_b") if ev.get("overhead_b") is not None else "",
                   storage_wait_ms=ev.get("storage_wait_ms") if ev.get("storage_wait_ms") is not None else "",
                   delivered=(ev.get("delivered") if ev.get("delivered") is not None else "") if verified_ratio else "",
                   sent=(ev.get("sent") if ev.get("sent") is not None else "") if verified_ratio else "",
                   delivery_evidence=ev.get("delivery_evidence") or "",
                   clock_quality=ev.get("clock_quality") or "",
                   evidence_json=json.dumps(d, ensure_ascii=False),
                   rtt_ms=self.app_stats[app]["rtt"] if self.app_stats[app]["rtt"] is not None else "")
        self.metric_rows.append(row)
        self.runs_lbl.config(text=f"{len(self.metric_rows)} measurement records")
        self._touch(ev["ts"])


# --------------------------------------------------------------------------- entry point
def main():
    ap = argparse.ArgumentParser(description="Mars Rover Mission Control — evidence-aware CoAP/BPv7")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="SIMULATED visual demonstration only")
    mode.add_argument("--live", action="store_true", help="connect to existing Rover AAP2/CoAP engine")
    mode.add_argument("--preview", action="store_true", help="display UI without generating data")
    ap.add_argument("--engine", help="path to EXISTING working Rover NodeA engine .py; required with --live")
    ap.add_argument("--socket", default="/tmp/ud3tn-ipn3-lab.aap2.sock")
    ap.add_argument("--measurements-jsonl", help="optional external VERIFIED metrics JSONL for Earth/Satellite evidence")
    ap.add_argument("--live-capture", action="store_true", help="enable read-only external TShark observation listener")
    ap.add_argument("--capture-port", type=int, default=56786)
    ap.add_argument("--capture-bind", default="192.168.100.3", help="Rover intnet IP for UDP observations")
    ap.add_argument("--capture-jsonl", default="~/ietf127_evidence/live_metrics.jsonl")
    ap.add_argument("--sol", type=int, default=42)
    ap.add_argument("--banner")
    ap.add_argument("--images")
    ap.add_argument("--event", default="IETF 127 Hackathon")
    args = ap.parse_args()

    bridge = MissionBridge()
    backend = None
    if args.demo:
        backend = DemoBackend(bridge, sol=args.sol)
        app = MissionControl(bridge, on_send=backend.send, on_toggle_link=backend.toggle_link,
                             mode="DEMO", sol=args.sol, banner=args.banner,
                             images_dir=args.images, event=args.event)
    elif args.live:
        if not args.engine:
            ap.error("--live requires --engine pointing to the real working NodeA file")
        from rover_live_backend import LiveBackend, MetricsFeed
        backend = LiveBackend(bridge, engine_path=args.engine, socket_path=args.socket,
                              sol=args.sol)
        app = MissionControl(bridge, on_send=backend.send, mode="LIVE",
                             sol=args.sol, banner=args.banner,
                             images_dir=args.images, event=args.event)
        if args.live_capture and args.measurements_jsonl:
            ap.error("Choose --live-capture OR --measurements-jsonl, not both")
        if args.live_capture:
            from live_metrics_hub import LiveMetricsHub
            app.hub = LiveMetricsHub(bridge, args.capture_jsonl, args.capture_bind, args.capture_port)
            try:
                app.hub.start()
            except OSError as exc:
                ap.error(f"Unable to bind LIVE metrics UDP listener: {exc}")
            app.hub.attach_backend(backend)
        backend.start()
        if args.live_capture:
            # The inherited MetricsFeed calls its BP-payload comparator
            # "json_bytes". Convert only internally: the JSONL records
            # preserve the correct bp_payload_bytes terminology.
            class CaptureMetricsFeed(MetricsFeed):
                def _handle(self, item):
                    if item.get("frame_association_verified") is True and "bp_payload_bytes" in item:
                        item = dict(item)
                        item["json_bytes"] = item["bp_payload_bytes"]
                    return super()._handle(item)
            app.feed = CaptureMetricsFeed(bridge, str(app.hub.output_path))
            app.feed.start()
        elif args.measurements_jsonl:
            app.feed = MetricsFeed(bridge, args.measurements_jsonl)
            app.feed.start()
    else:
        app = MissionControl(bridge, mode="PREVIEW", sol=args.sol,
                             banner=args.banner, images_dir=args.images, event=args.event)
    def close():
        if args.live:
            backend.stop()
            if hasattr(app, "feed"):
                app.feed.stop()
            if hasattr(app, "hub"):
                app.hub.stop()
        app.destroy()
    app.protocol("WM_DELETE_WINDOW", close)
    app.mainloop()


if __name__ == "__main__":
    main()
