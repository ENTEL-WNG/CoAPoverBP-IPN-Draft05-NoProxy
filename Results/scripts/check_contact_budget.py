#!/usr/bin/env python3
"""Necessary contact-capacity check; not proof NSTART>1 is congestion-safe."""
import argparse
p=argparse.ArgumentParser(description='Assess necessary contact byte capacity for controlled NSTART=2')
p.add_argument('--link-bps',type=float,required=True,help='measured bottleneck rate in bits/s')
p.add_argument('--contact-s',type=float,required=True,help='measured usable ON duration in seconds')
p.add_argument('--bundle-upper-b',type=int,required=True,help='conservative full on-wire size for a Single bundle')
p.add_argument('--backlog-b',type=int,required=True,help='current queued bytes on bottleneck link')
p.add_argument('--safety-fraction',type=float,default=.5)
p.add_argument('--nstart',type=int,choices=[1,2],default=1)
a=p.parse_args()
if a.link_bps<=0 or a.contact_s<=0 or a.bundle_upper_b<=0 or a.backlog_b<0 or not 0<a.safety_fraction<=1:
    p.error('Input values must be positive; safety-fraction within (0,1]')
usable=a.link_bps*a.contact_s/8*a.safety_fraction
projected=a.nstart*a.bundle_upper_b+a.backlog_b
print('Available conservative contact budget: %.1f B'%usable)
print('Projected outstanding + queued bytes: %d B'%projected)
if projected>usable: print('FAIL: projected bytes exceed conservative contact budget; do not raise NSTART.')
else: print('Capacity screen passes. This is NOT proof of congestion-control safety.')
print('Also evaluate RTT tail, loss, retransmits, queue growth, outages, and reverse-path constraints before NSTART=2.')
