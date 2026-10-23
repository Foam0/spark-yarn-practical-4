#!/usr/bin/env python3
"""Держит Quick Tunnels, обновляет nginx и карту публичных URL после старта."""
import argparse
import json
import pathlib
import re
import signal
import subprocess
import threading
import time

p = argparse.ArgumentParser()
p.add_argument("--internal-host", required=True)
p.add_argument("--public-host", required=True)
p.add_argument("--endpoints", required=True)
p.add_argument("--state-dir", default="/var/lib/hadoop-web")
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parent.parent
state = pathlib.Path(a.state_dir)
state.mkdir(parents=True, exist_ok=True)
endpoints = json.loads(pathlib.Path(a.endpoints).read_text())
ports = {s["name"]: s["port"] for s in endpoints}
ports["portal"] = 80
processes = {}
urls = {}
ready = set()
lock = threading.Lock()

def read_output(name, proc):
    for line in proc.stdout:
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        with lock:
            if match:
                urls[name] = match.group()
                print(f"{name}: {urls[name]}", flush=True)
            if "Registered tunnel connection" in line:
                ready.add(name)
        if "ERR" in line:
            print(f"{name}: {line.strip()}", flush=True)

def stop(*args):
    for proc in processes.values():
        proc.terminate()
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    for name, port in ports.items():
        proc = subprocess.Popen(["/usr/local/bin/cloudflared", "--no-autoupdate", "tunnel", "--protocol", "http2", "--url", f"http://127.0.0.1:{port}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        processes[name] = proc
        threading.Thread(target=read_output, args=(name, proc), daemon=True).start()
        time.sleep(1)
    deadline = time.monotonic() + 180
    while True:
        if any(proc.poll() is not None for proc in processes.values()):
            raise RuntimeError("Один из туннелей остановился")
        with lock:
            if len(urls) == len(ports) and len(ready) == len(ports):
                break
        if time.monotonic() > deadline:
            raise RuntimeError("Не удалось запустить все туннели за 180 секунд")
        time.sleep(1)
    temp = state / "public-urls.tmp"
    temp.write_text(json.dumps(urls, indent=2))
    public = state / "public-urls.json"
    temp.replace(public)
    subprocess.run(["python3", str(root / "scripts/render-nginx.py"), "--internal-host", a.internal_host, "--public-host", a.public_host, "--endpoints", a.endpoints, "--public-urls", str(public), "--output-dir", str(state)], check=True)
    subprocess.run(["install", "-m", "644", str(state / "hadoop-lab.conf"), "/etc/nginx/sites-available/hadoop-lab"], check=True)
    subprocess.run(["install", "-m", "644", str(state / "index.html"), "/var/www/hadoop-lab/index.html"], check=True)
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print("Все HTTPS-интерфейсы опубликованы; адреса: " + str(public), flush=True)
    while True:
        if any(proc.poll() is not None for proc in processes.values()):
            raise RuntimeError("Туннель завершился; systemd восстановит публикацию с новыми URL")
        time.sleep(5)
finally:
    for proc in processes.values():
        if proc.poll() is None:
            proc.terminate()
