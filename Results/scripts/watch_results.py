#!/usr/bin/env python3
"""Re-render SVG results every N seconds while a run is active. Ctrl+C stops only the watcher."""
import argparse
import subprocess
import sys
import time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--interval',type=float,default=10)
p.add_argument('--nstart',type=int,choices=(1,2),default=1)
a=p.parse_args()
script=Path(__file__).with_name('generate_results.py')
try:
    while True:
        subprocess.run([sys.executable,str(script),'--nstart',str(a.nstart)],check=False)
        time.sleep(max(3,a.interval))
except KeyboardInterrupt:
    print('Results watcher stopped; GUI and capture agents unaffected.')
