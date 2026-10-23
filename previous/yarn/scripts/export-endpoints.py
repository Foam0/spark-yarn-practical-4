#!/usr/bin/env python3
"""Запускать на сервере Docker. Экспортирует адреса для nginx на edge."""
import json
import subprocess

services = {
    "namenode": (9870, 9870), "secondarynamenode": (9868, 9868),
    "datanode1": (9864, 9864), "datanode2": (9864, 9865), "datanode3": (9864, 9866),
    "resourcemanager": (8088, 8088), "nodemanager1": (8042, 8042),
    "nodemanager2": (8042, 8043), "historyserver": (19888, 19888),
}
ids = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
entries = []
for container in containers:
    service = container["Config"].get("Labels", {}).get("com.docker.compose.service")
    if service not in services:
        continue
    internal, external = services[service]
    addresses = {service, container["Config"]["Hostname"]}
    for network in container["NetworkSettings"]["Networks"].values():
        addresses.add(network["IPAddress"])
    entries.append({"name": service, "port": external, "internal_port": internal,
                    "addresses": sorted(addresses)})
assert len(entries) == len(services), "Должны работать все девять сервисов HDFS и YARN"
print(json.dumps(entries, indent=2))
