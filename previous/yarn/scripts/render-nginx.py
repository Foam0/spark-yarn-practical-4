#!/usr/bin/env python3
"""Генерирует proxy-конфигурацию и страницу со ссылками на интерфейсы."""
import argparse
import html
import ipaddress
import json
import pathlib
import re

p = argparse.ArgumentParser()
p.add_argument("--internal-host", required=True)
p.add_argument("--public-host", required=True)
p.add_argument("--endpoints", required=True)
p.add_argument("--output-dir", required=True)
p.add_argument("--public-urls", help="JSON: имя сервиса → внешний HTTPS URL; для исходящих туннелей")
a = p.parse_args()
ipaddress.ip_address(a.internal_host)
if not re.fullmatch(r"[a-zA-Z0-9.-]+", a.public_host):
    raise SystemExit("public-host должен быть IP или DNS-именем")
services = json.loads(pathlib.Path(a.endpoints).read_text())
public_urls = json.loads(pathlib.Path(a.public_urls).read_text()) if a.public_urls else {}
out = pathlib.Path(a.output_dir)
out.mkdir(parents=True, exist_ok=True)
rewrites = []
for s in services:
    for address in s["addresses"]:
        if not re.fullmatch(r"[a-zA-Z0-9.-]+", address):
            raise SystemExit("Недопустимый внутренний адрес")
        target = public_urls.get(s["name"], f'http://{a.public_host}:{s["port"]}')
        rewrites.append((f'{address}:{s["internal_port"]}', target))
blocks = []
for s in services:
    lines = [f"server {{", f"  listen {s['port']};", "  server_name _;", "  location / {",
             f"    proxy_pass http://{a.internal_host}:{s['port']};",
             "    proxy_http_version 1.1;", '    proxy_set_header Host $http_host;',
             "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
             "    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;",
             '    proxy_set_header Accept-Encoding "";',
             "    proxy_read_timeout 120s;", "    limit_except GET HEAD { deny all; }",
             "    sub_filter_once off;", "    sub_filter_types application/json application/javascript text/javascript;"]
    for source, target in rewrites:
        # HTML, JSON and JS contain links both with and without a protocol.
        lines.append(f"    sub_filter 'http://{source}' '{target}';")
        lines.append(f"    sub_filter 'https://{source}' '{target}';")
        lines.append(f"    sub_filter '{source}' '{target.removeprefix('https://').removeprefix('http://')}';")
        lines.append(f"    proxy_redirect http://{source}/ {target}/;")
    if public_urls:
        # Hadoop может создавать Location из входного Host, добавляя http.
        public_host = public_urls[s['name']].removeprefix('https://')
        lines.append(f"    proxy_redirect http://{public_host}/ https://{public_host}/;")
        # Меняем только отдельные строки протокола в JS: пространства имён SVG
        # http://www.w3.org/2000/svg должны остаться исходными.
        lines.append('    sub_filter \'"http://"\' \'"https://"\';')
        lines.append('    sub_filter "\'http://\'" "\'https://\'";')
    scheme = "https" if public_urls else "http"
    lines.append(f'    sub_filter \'n.dnWebAddress = "http://" + dnHost + ":" + port;\' \'n.dnWebAddress = "{scheme}://" + n.infoAddr;\';')
    lines += ["  }", "}"]
    blocks.append("\n".join(lines))
blocks.append('''server {
  listen 80;
  server_name _;
  root /var/www/hadoop-lab;
  location / { limit_except GET HEAD { deny all; } try_files $uri $uri/ =404; }
}''')
(out / "hadoop-lab.conf").write_text("\n\n".join(blocks) + "\n")
labels = {"namenode": "HDFS NameNode", "secondarynamenode": "HDFS SecondaryNameNode",
          "datanode1": "HDFS DataNode 1", "datanode2": "HDFS DataNode 2", "datanode3": "HDFS DataNode 3",
          "resourcemanager": "YARN ResourceManager", "nodemanager1": "YARN NodeManager 1",
          "nodemanager2": "YARN NodeManager 2", "historyserver": "MapReduce JobHistoryServer"}
links = []
for s in services:
    url = public_urls.get(s["name"], f'http://{a.public_host}:{s["port"]}')
    links.append(f'<li><a href="{html.escape(url)}/">{html.escape(labels[s["name"]])}</a></li>')
links = "\n".join(links)
(out / "index.html").write_text('''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hadoop — учебный кластер</title>
<style>body{font:18px system-ui;max-width:760px;margin:64px auto;padding:0 24px;background:#f5f7fa;color:#172b4d}h1{font-size:32px}li{margin:16px 0}a{color:#075abd}small{color:#52647c}</style>
<h1>Hadoop — учебный кластер</h1><p>Веб-интерфейсы HDFS, YARN и истории MapReduce.</p><ul>''' + links + '</ul><small>Интерфейсы доступны для просмотра.</small></html>')
