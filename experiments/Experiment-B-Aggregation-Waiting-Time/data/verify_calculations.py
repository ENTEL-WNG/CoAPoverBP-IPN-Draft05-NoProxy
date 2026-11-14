#!/usr/bin/env python3
"""Verify Experiment B values from user-pasted event-log excerpts.
Uses only the Python standard library and reads no VM services or network resources.
"""
from pathlib import Path
import json, csv
root=Path(__file__).resolve().parent
files=sorted((root/'event_log_excerpts').glob('*_events_EXCERPT.jsonl'))
assert len(files)==4, 'Expected four run excerpts'
for i,path in enumerate(files,1):
    events=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    queued=[x for x in events if x['event']=='queued']
    submitted=[x for x in events if x['event']=='submitted']
    replies=[x for x in events if x['event']=='response']
    assert len(queued)==2 and len(replies)==2 and all(x['matched'] for x in replies)
    s1=next(x for x in submitted if queued[0]['token'] in x['tokens'])
    s2=next(x for x in submitted if queued[1]['token'] in x['tokens'])
    r1=next(x for x in replies if queued[0]['token']==x['token'])
    wait1=s1['time_epoch']-queued[0]['time_epoch']
    wait2=s2['time_epoch']-queued[1]['time_epoch']
    nbundles=len(submitted)
    tcp_data=352 if nbundles==1 else 392
    saved=392-tcp_data
    print(f'B{i} {path.name}: first wait={wait1:.6f}s; second wait={wait2:.6f}s; '
          f'bundles={nbundles}; TCP bytes={tcp_data}; saved={saved}')
    if r1['time_epoch'] < s1['time_epoch']:
        print(f'  TIMESTAMP WARNING: first response precedes submitted by '
              f'{1000*(s1["time_epoch"]-r1["time_epoch"]):.3f} ms')
print('Verified log arithmetic. The Wireshark byte counts were transcribed from screenshots.')
