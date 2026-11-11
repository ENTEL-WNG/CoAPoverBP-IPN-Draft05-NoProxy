#!/usr/bin/env python3
"""Generate research tables and SVG charts from the REAL live capture evidence.

Stdlib only (Python 3.8+). Never invents unavailable measurements.
Usage: python3 Results/scripts/generate_results.py --root Results
"""
import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

PALETTE = {'safety': '#008f85', 'science': '#db7625', 'navy': '#1b2a41',
           'blue': '#4267a5', 'muted': '#63758d', 'gray': '#f2f5f8'}


def read_jsonl(path):
    data = []
    if path is None or not Path(path).exists():
        return data
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    data.append(item)
            except (ValueError, TypeError):
                print('Skipped invalid JSON line %d: %s' % (i, path))
    return data


def svg_plot(path, title, subtitle, data, mode='line', xlabel='Observation', ylabel='', color='#008f85',
             annotation='', limit=None):
    width, height, left, right, top, bottom = 1040, 470, 95, 35, 96, 84
    pw, ph = width - left - right, height - top - bottom
    els = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,DejaVu Sans,sans-serif}</style>',
           f'<text x="42" y="42" fill="{PALETTE["navy"]}" font-size="24" font-weight="bold">{escape(title)}</text>',
           f'<text x="42" y="67" fill="{PALETTE["muted"]}" font-size="13">{escape(subtitle)}</text>']
    if not data:
        els += ['<rect x="95" y="120" width="850" height="220" rx="12" fill="#f2f5f8"/>',
                '<text x="520" y="220" font-size="21" text-anchor="middle" fill="#63758d">Not yet measured</text>',
                '<text x="520" y="252" font-size="14" text-anchor="middle" fill="#63758d">Run the live capture; regenerate charts afterward.</text>', '</svg>']
        path.write_text('\n'.join(els), encoding='utf8');return
    vals = [float(v) for _, v in data]
    ymax = max(max(vals) * 1.12, (float(limit) * 1.1) if limit is not None else 0, 0.01)
    ymin = min(0.0, min(vals))
    if ymax <= ymin: ymax = ymin+1
    for g in range(5):
        y = top + ph - (g/4)*ph
        v = ymin + (ymax-ymin)*g/4
        els.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="#e1e7ed"/>')
        els.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-size="12" fill="#63758d">{v:.2f}</text>')
    els.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+ph}" stroke="#677b8e"/>')
    els.append(f'<line x1="{left}" y1="{top+ph}" x2="{left+pw}" y2="{top+ph}" stroke="#677b8e"/>')
    if limit is not None:
        ly = top+ph-(float(limit)-ymin)/(ymax-ymin)*ph
        els.append(f'<line x1="{left}" y1="{ly:.2f}" x2="{left+pw}" y2="{ly:.2f}" stroke="#d04444" stroke-width="2" stroke-dasharray="7 5"/>')
        els.append(f'<text x="{left+pw-5}" y="{ly-7:.2f}" text-anchor="end" fill="#d04444" font-size="12">NSTART / configured cap = {limit}</text>')
    n = len(data)
    positions = [left + (i+0.5)*pw/max(1,n) for i in range(n)] if mode=='bar' else [left+(i*pw/max(1,n-1)) for i in range(n)]
    if mode == 'bar':
        bw = max(12, min(130, pw/(n*1.7)))
        for (lbl,v),x in zip(data,positions):
            y=top+ph-(float(v)-ymin)/(ymax-ymin)*ph
            els.append(f'<rect x="{x-bw/2:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{top+ph-y:.2f}" rx="4" fill="{color}"/>')
            els.append(f'<text x="{x:.1f}" y="{y-7:.1f}" font-size="13" text-anchor="middle" fill="{PALETTE["navy"]}">{v:g}</text>')
    else:
        points=[]
        for x, (_, v) in zip(positions,data):
            y=top+ph-(float(v)-ymin)/(ymax-ymin)*ph
            points.append(f'{x:.2f},{y:.2f}')
        if len(points)>1:
            els.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>')
        for (lbl,v),x in zip(data,positions):
            y=top+ph-(float(v)-ymin)/(ymax-ymin)*ph
            els.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')
    stride=max(1,math.ceil(n/9))
    for i,((label,_),x) in enumerate(zip(data,positions)):
        if i % stride==0 or i==n-1:
            label=str(label)
            if len(label)>13:label=label[:12]+'…'
            els.append(f'<text x="{x:.1f}" y="{top+ph+22}" font-size="11" text-anchor="middle" fill="#63758d">{escape(label)}</text>')
    els.append(f'<text x="{left+pw/2}" y="{height-39}" font-size="13" text-anchor="middle" fill="#1b2a41">{escape(xlabel)}</text>')
    els.append(f'<text transform="translate(26 {top+ph/2}) rotate(-90)" font-size="13" text-anchor="middle" fill="#1b2a41">{escape(ylabel)}</text>')
    if annotation:
        els.append(f'<text x="42" y="{height-12}" font-size="11" fill="#63758d">{escape(annotation[:140])}</text>')
    path.write_text('\n'.join(els+['</svg>']), encoding='utf8')


def write_csv(path, rows, headers):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf8') as f:
        w=csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows([{k:r.get(k,'') for k in headers} for r in rows])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--events',help='specific run events JSONL; default latest in Results/raw')
    ap.add_argument('--metrics',help='specific run metrics JSONL')
    ap.add_argument('--nstart',type=int,choices=(1,2),default=None)
    args=ap.parse_args()
    root=Path(args.root).expanduser().resolve()
    raw=root/'raw'; charts=root/'charts'; tables=root/'tables'
    charts.mkdir(parents=True,exist_ok=True);tables.mkdir(parents=True,exist_ok=True)
    ev_file=Path(args.events) if args.events else next(iter(sorted(raw.glob('*_events.jsonl'),key=lambda p:p.stat().st_mtime,reverse=True)), None)
    if not ev_file:
        print('No run events found; generating clearly labeled empty chart templates.')
        ev=[]; metrics=[]; base='no_run'
    else:
        ev=read_jsonl(ev_file)
        base=ev_file.name.replace('_events.jsonl','')
        metrics_file=Path(args.metrics) if args.metrics else ev_file.with_name(base+'.jsonl')
        metrics=read_jsonl(metrics_file)
    # Every figure is derived from the observed run only, never from synthetic values.
    responses=[r for r in ev if r.get('event')=='response' and r.get('matched') is True and isinstance(r.get('rtt_ms'),(int,float))]
    sent=[r for r in ev if r.get('event')=='submitted']
    receipts=[r for r in ev if r.get('event')=='earth_receipt']
    write_csv(tables/'matched_responses.csv',responses,['timestamp_utc','app','code','token','rtt_ms'])
    write_csv(tables/'bundle_submissions.csv',sent,['timestamp_utc','app','bundle_kind','members','bp_payload_bytes','tokens'])
    write_csv(tables/'verified_earth_receipts.csv',receipts,['timestamp_utc','app','bundle_id','members','bp_payload_bytes','earth_recv_utc'])
    # Each record from the live collector is a rolling measurement; show actual window value and label it TCP link rate.
    rates=[]; timing=[]; overhead=[]
    for m in metrics:
        seconds=m.get('window_seconds'); b=m.get('window_received_bytes')
        t=m.get('time_epoch')
        if isinstance(seconds,(float,int)) and seconds>=1 and isinstance(b,(float,int)) and b>=0 and isinstance(t,(int,float)):
            rates.append((t, 8*b/(1000*seconds)))
        if isinstance(m.get('associated_captured_frame_bytes'),(int,float)) and isinstance(m.get('bp_payload_bytes'),(int,float)) and m.get('frame_association_verified') is True:
            overhead.append((len(overhead)+1, m['associated_captured_frame_bytes']-m['bp_payload_bytes']))
        if isinstance(m.get('satellite_receive_monotonic_ns'),(int,float)) and isinstance(m.get('satellite_forward_monotonic_ns'),(int,float)):
            timing.append((len(timing)+1,(m['satellite_forward_monotonic_ns']-m['satellite_receive_monotonic_ns'])/1e6))
    rtt=[('%s-%d'%(r.get('app','?'),i+1),float(r['rtt_ms'])) for i,r in enumerate(responses)]
    svg_plot(charts/'application_rtt.svg','Application round-trip time','Rover-observed matched CoAP responses',rtt,
             ylabel='Application RTT (ms)',xlabel='Matched response sequence')
    kinds=Counter(r.get('bundle_kind','Unverified') for r in sent)
    svg_plot(charts/'single_vs_aggregate.svg','CoAP over BP: transmission types','Based on submitted bundle_kind callback (not button presses)',
             [('SINGLE',kinds.get('Single',0)),('AGGREGATE',kinds.get('Aggregate',0)),('UNKNOWN',kinds.get('Unverified',0))] if sent else [],
             mode='bar',ylabel='Bundles submitted',xlabel='BP payload classification',color=PALETTE['blue'])
    svg_plot(charts/'earth_receipt_progress.svg','Verified Earth receipt progress','In-run totals; not a final loss metric until the observation horizon expires',
             [('submitted',sum(int(r.get('members') or 0) for r in sent)),('Earth receipts',sum(int(r.get('members') or 0) for r in receipts))] if sent else [],
             mode='bar',ylabel='Number of CoAP Singles',xlabel='Observation type',color=PALETTE['safety'])
    # Sample rate at most 50 evenly across run to avoid an unreadable plot.
    if len(rates)>50: rates=rates[::max(1,len(rates)//50)]
    svg_plot(charts/'satellite_earth_link_rate.svg','Satellite → Earth TCPCL traffic','Five-second rolling window of TCP payload bytes (NOT CoAP goodput)',
             [(datetime.fromtimestamp(t).strftime('%H:%M:%S'),v) for t,v in rates],
             ylabel='TCPCL link rate (kbps)',xlabel='Recorded interval',color=PALETTE['blue'])
    svg_plot(charts/'data_bearing_overhead.svg','Data-bearing capture overhead','Ethernet frame bytes minus BPv7 payload; ACKs excluded',
             [('bundle %d'%i,v) for i,v in overhead], mode='bar', ylabel='Bytes', xlabel='Verified frame association',color=PALETTE['science'])
    # Outstanding timeline: counts queued requests until matched responses, per-app.
    ordered=sorted([x for x in ev if x.get('event') in ('queued','response')],key=lambda x:float(x.get('time_epoch') or 0))
    inflight=defaultdict(set); timeline=[]; max_per_app=defaultdict(int)
    for r in ordered:
        app=r.get('app','unknown'); token=str(r.get('token',''))
        if not token: continue
        if r['event']=='queued': inflight[app].add(token)
        elif r['event']=='response' and r.get('matched') is True: inflight[app].discard(token)
        max_per_app[app]=max(max_per_app[app],len(inflight[app]))
        timeline.append((str(len(timeline)+1),max(len(x) for x in inflight.values())))
    if args.nstart is not None:
        limit = args.nstart
    elif ev_file and ev_file.with_name(base + '_config.json').exists():
        try:
            limit = int(json.loads(ev_file.with_name(base + '_config.json').read_text()).get('gui_cc_limit', 1))
        except (ValueError, OSError, TypeError):
            limit = 1
    else:
        limit = 1
    svg_plot(charts/'outstanding_nstart.svg','Outstanding interactions vs NSTART','Each app is a distinct CoAP client; trace counts outstanding tokens per app',
             timeline,ylabel='Max outstanding per application', xlabel='Request/response event sequence',limit=limit,color=PALETTE['science'])
    violation=any(v>limit for v in max_per_app.values())
    flags=[f'Events file: {str(ev_file) if ev_file else "none"}',f'Matched application RTTs: {len(responses)}',
           f'Bundles submitted: {len(sent)}; SINGLE={kinds.get("Single",0)}, AGGREGATE={kinds.get("Aggregate",0)}',
           f'Verified Earth receipt events: {len(receipts)}',
           f'Max outstanding tokens by application: {dict(max_per_app)}; NSTART report limit: {limit}',
           f'Outstanding cap violations in observed event trace: {"YES – INVESTIGATE" if violation else "none detected (trace only)"}',
           f'Link-rate records: {len(rates)}',f'Verified overhead records: {len(overhead)}']
    (root/'SUMMARY.md').write_text('# IETF 127 Results — '+base+'\n\n'+'\n'.join('- '+line for line in flags)+
        '\n\n## Interpretation safeguards\n\n'
        '- A successful CoAP response is not by itself an Earth receipt count; only BPv7-correlated receipts are used.\n'
        '- The percentage received/submitted is provisional until a settled run has elapsed.\n'
        '- Missing one-way delay/storage wait remains unmeasured; do not replace N/A with zero.\n'
        '- Packet-level link rate is NOT CoAP application goodput.\n'
        '- Frame-overhead plot excludes reverse TCP ACKs and is NOT an estimate of every protocol layer.\n'
        '- NSTART=2 requires separately documented congestion-control justification and safety mechanism; a guard alone is not proof of safety.\n',encoding='utf8')
    print('\n'.join(flags))
    print('Charts saved in:',charts)

if __name__=='__main__': main()
