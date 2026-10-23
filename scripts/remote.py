#!/usr/bin/env python3
"""Run a stdin shell script on a team-27 node through edge without copying keys."""
from pathlib import Path
import shlex
import subprocess
import sys

host = sys.argv[1]
if host not in ['team-27-00', 'team-27-nn', 'team-27-01']:
    raise SystemExit('Unknown team-27 node')
script = shlex.join(['bash', '-c', sys.stdin.read()])
inner = ['ssh', '-i', '.ssh/team_internal', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', f'team@{host}', script]
raise SystemExit(subprocess.run(['ssh', '-i', str(Path.home()/'.ssh/macbook_ed25519'), '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', 'team@2.59.81.216', shlex.join(inner)], stdin=subprocess.DEVNULL).returncode)
