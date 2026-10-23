#!/usr/bin/env python3
"""Проверка с внешней машины: страницы, REST, ссылки, запрет записи."""
import argparse
import json
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("host", help="Внешний IP/DNS edge-узла, без http://")
p.add_argument("--public-urls", help="JSON с HTTPS-адресами исходящих туннелей")
a = p.parse_args()
urls = json.load(open(a.public_urls)) if a.public_urls else {}
ports = {80: 'portal', 9870: 'namenode', 9868: 'secondarynamenode', 9864: 'datanode1',
         9865: 'datanode2', 9866: 'datanode3', 8088: 'resourcemanager', 8042: 'nodemanager1',
         8043: 'nodemanager2', 19888: 'historyserver'}
def base(port):
    return urls.get(ports[port], f"http://{a.host}:{port}")
def get(port, path="/"):
    url = base(port) + path
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.status == 200, url
        return response.read().decode()

for port in (80, 9870, 9868, 9864, 9865, 9866, 8088, 8042, 8043, 19888):
    assert get(port), f"Пустая страница {port}"
    print(f"{base(port)}/ — HTTP 200", flush=True)
nodes = json.loads(get(8088, "/ws/v1/cluster/nodes"))["nodes"]["node"]
assert len(nodes) == 2 and all(n["state"] == "RUNNING" and not n["healthReport"] for n in nodes)
assert {n["nodeHTTPAddress"] for n in nodes} == {base(port).removeprefix('https://').removeprefix('http://') for port in (8042, 8043)}
for port in (8042, 8043):
    assert json.loads(get(port, "/ws/v1/node/info"))["nodeInfo"]["nodeHealthy"]
assert json.loads(get(19888, "/ws/v1/history/info"))["historyInfo"]["hadoopVersion"] == "3.4.1"
bean = json.loads(get(9870, "/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem"))["beans"][0]
assert bean["NumLiveDataNodes"] == 3 and bean["NumDeadDataNodes"] == 0
assert bean["MissingBlocks"] == 0 and bean["CorruptBlocks"] == 0
apps = json.loads(get(8088, "/ws/v1/cluster/apps"))
completed = [x for x in (apps.get("apps") or {}).get("app", []) if x["finalStatus"] == "SUCCEEDED"]
assert completed, "Нет успешно выполненного YARN-задания"
for application in completed:
    tracking = application.get("trackingUrl", "")
    if tracking:
        assert tracking.startswith(base(19888)) or tracking.startswith(base(8088)), tracking
        with urllib.request.urlopen(tracking, timeout=20) as response:
            assert response.status == 200
for port in (9870, 8088, 8042, 19888):
    try:
        urllib.request.urlopen(urllib.request.Request(base(port) + '/', data=b"", method="POST"), timeout=20)
    except urllib.error.HTTPError as e:
        assert e.code == 403, (port, e.code)
    else:
        raise AssertionError(f"POST не запрещён на {port}")
print("Внешние интерфейсы и ссылки исправны; HDFS и YARN здоровы; запись через proxy запрещена.")
