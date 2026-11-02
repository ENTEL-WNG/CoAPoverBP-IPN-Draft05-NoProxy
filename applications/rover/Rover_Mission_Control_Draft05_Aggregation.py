"""Mars Rover Mission Control v2 — visible science send/receive telemetry.

Uses two real Draft-05 CoAP-over-BPv7 clients.

IPN Safety  ipn:0.1.10 -> Earth ipn:0.3.64, GET /mission/safety-guidance
IPN Science ipn:0.1.11 -> Earth ipn:0.3.64, POST /science/observations

Run on the Rover Ubuntu VM. Requires the user's existing modified aiocoap fork,
AAP2 python-ud3tn-utils, Pillow and protobuf. No simulated networking: these
buttons send real AAP2 BundleADUs to the local µD3TN daemon.

The mission CONTENT is simulated, but network delivery and responses are real.
"""
import asyncio
import importlib.util
import json
import queue
import threading
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps

# The Draft-05 engine imports ud3tn_utils and the local modified aiocoap fork.
from ud3tn_utils.aap2 import AAP2AsyncUnixClient

BASE = Path.home() / 'coapbp/experiments/ipn-hackathon-2026'
ENGINE = Path(__file__).resolve().with_name('NodeA_Mission_Draft05_Aggregation.py')
IMAGE = BASE / 'assets/mission.jpg'
SOCKET = '/tmp/ud3tn-ipn3-lab.aap2.sock'

COLORS = dict(bg='#091527', panel='#142941', white='#f5f7fa',
              muted='#b8cada', safety='#237e82', science='#b46f30',
              info='#7bc9d1', warn='#f2b56b')


def load_isolated_engine(name):
    """Separate Python module globals isolate MID/buffer/pending state per app."""
    if not ENGINE.is_file():
        raise FileNotFoundError('Draft-05 engine file missing: ' + str(ENGINE))
    spec = importlib.util.spec_from_file_location('mission_draft05_' + name, ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RoverBridge:
    def __init__(self):
        self.events = queue.Queue()
        self.loop = None
        self.ready = set()
        self.engines = {}
        self.stop_event = None
        self.thread = threading.Thread(target=self._thread_main, daemon=True)

    def start(self):
        self.thread.start()

    def emit(self, service, event, **data):
        self.events.put((service, event, data))

    def _thread_main(self):
        try:
            asyncio.run(self._main())
        except Exception as exc:
            self.emit('system', 'error', message=str(exc))

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.stop_event = asyncio.Event()
        tasks = []
        try:
            async with AsyncExitStack() as stack:
                # Two distinct AAP2 registrations. Each has a sender and an
                # independently subscribed receiver sharing its registration secret.
                for service in ('10', '11'):
                    name = 'Safety' if service == '10' else 'Science'
                    module = load_isolated_engine(service)
                    module.MID_STATE_FILE = str(Path.home() / 'coapbp/experiments/draft05-ipn/state' / ('rover_' + name.lower() + '_aggregation_mid_state.json'))
                    module.NSTART = 2  # Controlled aggregation experiment
                    module.load_mid_state()
                    module.EVENT_CALLBACK = lambda event, data, sid=service: self.emit(sid, event, **data)

                    sender = await stack.enter_async_context(AAP2AsyncUnixClient(SOCKET))
                    secret = await sender.configure(agent_id=service)
                    receiver = await stack.enter_async_context(AAP2AsyncUnixClient(SOCKET))
                    await receiver.configure(agent_id=service, subscribe=True, secret=secret)

                    module.coap_send_client = sender
                    module.coap_receive_client = receiver
                    self.engines[service] = module
                    tasks.append(asyncio.create_task(module.coap_receive_loop()))
                    self.ready.add(service)
                    self.emit(service, 'registered', eid='ipn:0.1.' + service)

                self.emit('system', 'ready', message='Both Draft-05 CoAP clients registered')
                tasks.append(asyncio.create_task(self._expire_pending()))
                await self.stop_event.wait()
                self.emit('system', 'stopping')
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.ready.clear()
            self.emit('system', 'stopped')

    async def _expire_pending(self):
        # Lost NON responses should not block NSTART=1 forever.
        # This laboratory timeout is the existing Draft-05 client's NON lifetime;
        # it must be re-evaluated for long DTN contact plans.
        import time
        while True:
            await asyncio.sleep(2)
            for service, module in self.engines.items():
                now = time.time()
                expired = [token for token, item in module.pending_requests.items()
                           if now - item['sent_time'] > module.NON_LIFETIME_SECONDS]
                for token in expired:
                    info = module.pending_requests.pop(token)
                    self.emit(service, 'timeout', token=token.hex(), mid=info['mid'])

    async def _transmit(self, service):
        if service not in self.ready:
            self.emit(service, 'error', message='Application not registered with µD3TN')
            return
        module = self.engines[service]
        # Experimental NSTART=2 per app; shared limit needs validation.
        if not module.nstart_space_available():
            self.emit(service, 'blocked', message=f'NSTART={module.NSTART}: interaction limit reached')
            return
        try:
            if service == '10':
                await module.queue_coap_request('get', resource_path='mission/safety-guidance')
            else:
                observation = {
                    'sol': 42,
                    'type': 'science_observation',
                    'source': 'simulated Mars rover',
                    'navigation_camera': 'dust obscures distant landmarks',
                    'atmospheric_dust_index': 0.87,
                    'battery_percent': 68,
                    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                }
                # The displayed telemetry is the SAME object encoded into the
                # CoAP POST payload, not a separately invented example.
                encoded_observation = json.dumps(
                    observation, separators=(',', ':')
                ).encode('utf-8')
                await module.queue_coap_request(
                    'post', resource_path='science/observations',
                    payload=encoded_observation
                )
                self.emit(service, 'science_payload',
                          observation=observation,
                          payload_bytes=len(encoded_observation))
            # Experimental aggregation: the engine flushes when
            # the buffer reaches 2 messages or its timer expires.
        except Exception as exc:
            self.emit(service, 'error', message=str(exc))

    def send(self, service):
        if self.loop is None or service not in self.ready:
            self.emit(service, 'error', message='AAP2 connection is not ready')
            return
        try:
            asyncio.run_coroutine_threadsafe(self._transmit(service), self.loop)
        except RuntimeError as exc:
            self.emit(service, 'error', message=str(exc))

    def stop(self):
        if self.loop is not None and self.stop_event is not None:
            try:
                self.loop.call_soon_threadsafe(self.stop_event.set)
            except RuntimeError:
                pass


def main():
    root = tk.Tk()
    root.title('Mars Rover Mission Control — Live CoAP over BPv7')
    root.geometry('910x690')
    root.minsize(680, 540)
    root.configure(bg=COLORS['bg'])

    # Scrollable content prevents the status line from being cut off on 768p VMs.
    canvas = tk.Canvas(root, bg=COLORS['bg'], highlightthickness=0)
    scroll = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    content = tk.Frame(canvas, bg=COLORS['bg'])
    content_id = canvas.create_window((0, 0), window=content, anchor='nw')
    content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(content_id, width=e.width))

    body = tk.Frame(content, bg=COLORS['bg'])
    body.pack(fill='both', expand=True, padx=19, pady=12)
    try:
        picture = Image.open(IMAGE).convert('RGB')
        picture = ImageOps.fit(picture, (860, 195), method=Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(picture)
        image_label = tk.Label(body, image=photo, bg=COLORS['bg'])
        image_label.image = photo
        image_label.pack(pady=(0, 8))
    except Exception as exc:
        tk.Label(body, text='Rover photograph missing: ' + str(exc),
                 fg=COLORS['warn'], bg=COLORS['bg']).pack(pady=8)

    tk.Label(body, text='MARS ROVER MISSION CONTROL',
             font=('Arial', 19, 'bold'), bg=COLORS['bg'], fg=COLORS['white']).pack()
    tk.Label(body, text='Draft-05 CoAP over BPv7  |  IPN Dual-Application Experiment',
             font=('Arial', 10), bg=COLORS['bg'], fg=COLORS['muted']).pack(pady=(3, 9))
    tk.Label(body, text='ROVER ipn:0.1.0  →  SATELLITE ipn:0.2.0  →  EARTH ipn:0.3.64',
             bg=COLORS['panel'], fg=COLORS['white'],
             padx=12, pady=9, font=('Arial', 10, 'bold')).pack(fill='x')

    reg_var = tk.StringVar(value='Safety: Connecting  |  Science: Connecting')
    tk.Label(body, textvariable=reg_var, font=('Arial', 10, 'bold'),
             bg=COLORS['panel'], fg=COLORS['info'], pady=8).pack(fill='x', pady=(7, 8))
    detail_var = tk.StringVar(value='Choose a Rover application to submit a real CoAP request.')
    buttons = tk.Frame(body, bg=COLORS['bg'])
    buttons.pack(fill='x', pady=(2, 6))
    bridge = RoverBridge()
    for service, title, color in (
            ('10', 'ROVER SAFETY\nGET  |  ipn:0.1.10', COLORS['safety']),
            ('11', 'ROVER SCIENCE\nPOST |  ipn:0.1.11', COLORS['science'])):
        btn = tk.Button(buttons, text=title, command=lambda s=service: bridge.send(s),
                        font=('Arial', 12, 'bold'), fg='white', bg=color,
                        padx=8, pady=13, relief='flat', cursor='hand2')
        btn.pack(side='left', fill='x', expand=True, padx=5)
    tk.Label(body, textvariable=detail_var, bg=COLORS['panel'],
             fg=COLORS['white'], font=('Arial', 10), anchor='w', justify='left',
             padx=13, pady=10, wraplength=820).pack(fill='x', pady=(5, 8))

    # Distinct science send/receive panels use live data from the request
    # created by RoverBridge and the actual, token-matched Earth response.
    science_header = tk.Frame(body, bg=COLORS['bg'])
    science_header.pack(fill='x', pady=(4, 5))
    tk.Label(science_header, text='SCIENCE TELEMETRY  /  SOL 42',
             bg=COLORS['bg'], fg=COLORS['white'],
             font=('Arial', 11, 'bold')).pack(side='left')
    tk.Label(science_header, text='SIMULATED SENSOR DATA  |  REAL BPv7 TRANSMISSION',
             bg=COLORS['bg'], fg=COLORS['muted'],
             font=('Arial', 8)).pack(side='right')

    science_panels = tk.Frame(body, bg=COLORS['bg'])
    science_panels.pack(fill='x', pady=(0, 9))
    science_panels.columnconfigure(0, weight=1, uniform='telemetry')
    science_panels.columnconfigure(1, weight=1, uniform='telemetry')

    sent_panel = tk.Frame(science_panels, bg=COLORS['panel'],
                          highlightbackground=COLORS['safety'],
                          highlightcolor=COLORS['safety'], highlightthickness=1)
    sent_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
    tk.Label(sent_panel, text='DATA SENT FROM ROVER',
             bg=COLORS['safety'], fg='white',
             font=('Arial', 10, 'bold'), padx=9, pady=6,
             anchor='w').pack(fill='x')
    science_sent_var = tk.StringVar(value=(
        'No observations submitted yet.\n'
        'Click ROVER SCIENCE to send a CoAP POST.'
    ))
    tk.Label(sent_panel, textvariable=science_sent_var,
             bg=COLORS['panel'], fg=COLORS['white'],
             font=('DejaVu Sans', 9), anchor='nw', justify='left',
             padx=10, pady=9, wraplength=365).pack(fill='both', expand=True)

    reply_panel = tk.Frame(science_panels, bg=COLORS['panel'],
                           highlightbackground=COLORS['science'],
                           highlightcolor=COLORS['science'], highlightthickness=1)
    reply_panel.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
    tk.Label(reply_panel, text='RESPONSE RECEIVED FROM EARTH',
             bg=COLORS['science'], fg='white',
             font=('Arial', 10, 'bold'), padx=9, pady=6,
             anchor='w').pack(fill='x')
    science_reply_var = tk.StringVar(value=(
        'No response received yet.\n'
        'Earth endpoint: ipn:0.3.64'
    ))
    tk.Label(reply_panel, textvariable=science_reply_var,
             bg=COLORS['panel'], fg=COLORS['white'],
             font=('DejaVu Sans', 9), anchor='nw', justify='left',
             padx=10, pady=9, wraplength=365).pack(fill='both', expand=True)

    tk.Label(body, text='LIVE BPv7 / CoAP EVENT LOG', bg=COLORS['bg'],
             fg=COLORS['white'], font=('Arial', 11, 'bold')).pack(anchor='w')
    log = tk.Text(body, height=9, bg='#09131f', fg='#c7dded',
                  insertbackground='white', wrap='word', font=('DejaVu Sans Mono', 9),
                  borderwidth=0, padx=9, pady=8)
    log.pack(fill='both', expand=True, pady=(5, 9))
    log.configure(state='disabled')
    statuses = {'10': 'Connecting', '11': 'Connecting'}
    names = {'10': 'SAFETY', '11': 'SCIENCE', 'system': 'SYSTEM'}

    def log_line(message):
        log.configure(state='normal')
        log.insert('end', datetime.now().strftime('%H:%M:%S') + '  ' + message + '\n')
        log.see('end')
        log.configure(state='disabled')

    def check_events():
        try:
            while True:
                service, event, data = bridge.events.get_nowait()
                who = names.get(service, service)
                if event == 'registered':
                    statuses[service] = 'Registered'
                    log_line(who + ': AAP2 registered ' + data['eid'])
                elif event == 'queued':
                    log_line('%s: CoAP %s queued | MID=%s Token=%s' %
                             (who, data['method'], data['mid'], data['token']))
                    if service == '11':
                        science_reply_var.set(
                            'Awaiting a matched Earth response...\n'
                            'Request token: ' + str(data['token']))
                elif event == 'science_payload':
                    # These displayed readings come from the very same dict
                    # that was serialized and queued in the actual CoAP POST.
                    observation = data['observation']
                    timestamp = observation['timestamp_utc']
                    science_sent_var.set(
                        'POST /science/observations\n'
                        'From ipn:0.1.11  →  To ipn:0.3.64\n'
                        'Sol: %s   |   Battery: %s%%\n'
                        'Dust index: %s\n'
                        'Camera: %s\n'
                        'Time (UTC): %s\n'
                        'JSON payload: %s bytes\n'
                        'Status: QUEUED (not yet delivered)' % (
                            observation['sol'], observation['battery_percent'],
                            observation['atmospheric_dust_index'],
                            observation['navigation_camera'], timestamp,
                            data['payload_bytes']))
                    log_line('SCIENCE: Prepared JSON observation: Sol %s, dust %s, battery %s%%, UTC %s' % (
                        observation['sol'], observation['atmospheric_dust_index'],
                        observation['battery_percent'], timestamp))
                elif event == 'submitted':
                    log_line('%s: %s BP bundle submitted locally (%s B); awaiting Earth response' %
                             (who, data['bundle_kind'], data['bytes']))
                    if service == '11':
                        science_sent_var.set(science_sent_var.get().replace(
                            'Status: QUEUED (not yet delivered)',
                            'Status: SUBMITTED to local µD3TN (delivery pending)'))
                elif event == 'response':
                    accepted = data['matched']
                    message = '%s: %s CoAP response %s from %s | Token=%s | %s' % (
                        who, 'MATCHED' if accepted else 'UNMATCHED', data['code'],
                        data['src'], data['token'], data['payload'])
                    log_line(message)
                    if accepted:
                        detail_var.set(message)
                        if service == '11':
                            science_reply_var.set(
                                'CoAP response: %s\n'
                                'From: %s  →  Rover ipn:0.1.11\n'
                                'Matching token: %s\n'
                                'Earth says: %s\n'
                                'Status: MATCHED response confirmed' % (
                                    data['code'], data['src'], data['token'],
                                    data['payload']))
                            science_sent_var.set(science_sent_var.get().replace(
                                'Status: SUBMITTED to local µD3TN (delivery pending)',
                                'Status: Earth response received'))
                    elif service == '11':
                        science_reply_var.set(
                            'UNMATCHED response from %s\nToken: %s\n'
                            'Not confirmation of this POST' % (
                                data['src'], data['token']))
                elif event == 'timeout':
                    log_line('%s: No response within lab timeout; MID=%s Token=%s' %
                             (who, data['mid'], data['token']))
                elif event in ('blocked', 'rejected', 'error', 'compat_warning'):
                    message = data.get('message') or data.get('reason') or 'Unknown error'
                    log_line(who + ': ' + event.upper() + ' — ' + message)
                    if event == 'error' and service in statuses:
                        statuses[service] = 'Error'
                elif event == 'ready':
                    log_line('Both independent IPN CoAP endpoints ready')
                elif event == 'stopped':
                    log_line('AAP2 clients stopped')
                else:
                    log_line(who + ': ' + event)
        except queue.Empty:
            pass
        reg_var.set('Safety: ' + statuses['10'] + '  |  Science: ' + statuses['11'])
        root.after(180, check_events)

    log_line('Network result labels: submitted locally != delivered to Earth')
    log_line('Safety/Science payloads are simulated Mars mission data')
    log_line('2.05 Content = GET data  |  2.01 Created = Science POST server response')
    bridge.start()
    root.after(180, check_events)

    def on_close():
        bridge.stop()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
