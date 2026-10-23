#!/usr/bin/env python3
"""Two live remote JDBC sessions with different names; verify their overlap."""
import os
from pathlib import Path
import subprocess
import time

os.chdir(Path(__file__).resolve().parents[1])
Path('logs').mkdir(exist_ok=True)
processes = []
files = []
try:
    for name, country in [('client_a', 'RU'), ('client_b', 'KZ')]:
        path = Path(f'logs/{name}.log')
        output = path.open('w')
        files.append(output)
        env = dict(os.environ, HIVE_CLIENT_USER=name)
        proc = subprocess.Popen(['scripts/beeline.sh'], env=env, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT, text=True)
        processes.append((proc, path, name))
        proc.stdin.write(f"SELECT '{name}_ready', logged_in_user(), current_user(), order_id, amount FROM practical3.orders WHERE dt='2026-10-01' AND country='{country}';\n")
        proc.stdin.flush()
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if any(proc.poll() is not None for proc, _, _ in processes):
            raise RuntimeError('A JDBC client exited before the overlap check')
        if all(f'{name}_ready\t' in path.read_text() for _, path, name in processes):
            break
        time.sleep(1)
    else:
        raise RuntimeError('Clients did not finish their first query within 120 seconds')
    # Each server-side established TCP socket is an independent remote JDBC client.
    sockets = subprocess.check_output(['ss', '-Hnt', 'state', 'established', '( sport = :10000 )'], text=True)
    count = len(sockets.strip().splitlines())
    if count < 2:
        raise RuntimeError(f'Expected >=2 live JDBC connections, got {count}')
    print('Two simultaneous remote JDBC sessions confirmed: client_a and client_b')
    print(sockets.strip())
    for proc, path, name in processes:
        proc.stdin.write('!quit\n')
        proc.stdin.close()
    for proc, path, name in processes:
        if proc.wait(timeout=30) != 0:
            raise RuntimeError(f'{name} exited with an error')
        print(f'--- {name} ---\n{path.read_text()}')
finally:
    for proc, _, _ in processes:
        if proc.poll() is None:
            proc.terminate()
    for f in files:
        f.close()
