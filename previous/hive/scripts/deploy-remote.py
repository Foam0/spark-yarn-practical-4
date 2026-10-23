#!/usr/bin/env python3
"""Run from your computer. Copy sources via edge; provision the team-27 lab."""
import argparse
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--edge', default='team@2.59.81.216')
p.add_argument('--key', default=str(Path.home()/'.ssh/macbook_ed25519'))
args = p.parse_args()
root = Path(__file__).resolve().parents[1]

def remote(host, script, data=None):
    if script == 'bash -s':
        script = shlex.join(['bash', '-c', data.decode()])
        data = b''
    inner = ['ssh', '-i', '.ssh/team_internal', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', f'team@{host}', script]
    return subprocess.run(['ssh', '-i', args.key, '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', args.edge, shlex.join(inner)], input=data, stdout=subprocess.PIPE, check=True).stdout

raw = remote('team-27-nn', 'sudo docker inspect $(sudo docker ps -q)')
containers = json.loads(raw)
hosts = {}
for c in containers:
    for net in c['NetworkSettings']['Networks'].values():
        for alias in net.get('Aliases') or []:
            if alias in ['namenode', 'datanode1', 'datanode2', 'datanode3', 'resourcemanager', 'historyserver', 'nodemanager1', 'nodemanager2']:
                hosts[alias] = net['IPAddress']
if len(hosts) != 8:
    raise SystemExit(f'Expected eight HDFS/YARN hosts, got {sorted(hosts)}')
subnet = json.loads(remote('team-27-nn', 'sudo docker network inspect hdfs-lab_hdfs'))[0]['IPAM']['Config'][0]['Subnet']

# Reach the Docker network through an encrypted private tunnel, with scoped firewall rules.
for host in ['team-27-nn', 'team-27-00']:
    remote(host, 'bash -s', b"set -e\nif ! command -v wg >/dev/null; then sudo apt-get update -qq; sudo apt-get install -y wireguard-tools >/dev/null; fi\nsudo mkdir -p /etc/wireguard\nif ! sudo test -s /etc/wireguard/hive.key; then sudo sh -c 'umask 077; wg genkey > /etc/wireguard/hive.key'; fi\n")
pubs = {host: remote(host, "sudo sh -c 'wg pubkey < /etc/wireguard/hive.key'").decode().strip() for host in ['team-27-nn', 'team-27-00']}
for host, address, peer, endpoint, allowed in [
    ('team-27-nn', '10.255.27.1/30', 'team-27-00', '10.27.0.12:51827', '10.255.27.2/32'),
    ('team-27-00', '10.255.27.2/30', 'team-27-nn', '10.27.0.11:51827', f'10.255.27.1/32,{subnet}')]:
    conf = f"[Interface]\nAddress = {address}\nListenPort = 51827\nTable = off\nPrivateKey = PLACEHOLDER\n[Peer]\nPublicKey = {pubs[peer]}\nEndpoint = {endpoint}\nAllowedIPs = {allowed}\nPersistentKeepalive = 25\n"
    script = f"sudo tee /etc/wireguard/wg-hive.conf >/dev/null <<'EOF'\n{conf}EOF\n"
    script += "sudo python3 -c \"from pathlib import Path; p=Path('/etc/wireguard/wg-hive.conf'); p.write_text(p.read_text().replace('PLACEHOLDER',Path('/etc/wireguard/hive.key').read_text().strip())); p.chmod(0o600)\"\n"
    script += 'sudo systemctl enable wg-quick@wg-hive\nsudo systemctl restart wg-quick@wg-hive\n'
    remote(host, 'bash -s', script.encode())
# Allow only the Hive tunnel address and required HDFS/YARN TCP ports.
forward = f'''#!/bin/bash
set -eu
iptables -t raw -C PREROUTING -i wg-hive -s 10.255.27.2 -d {subnet} -p tcp -m multiport --dports 8020,9870,9866,8030,8031,8032,8033,10020 -j ACCEPT 2>/dev/null || iptables -t raw -I PREROUTING 1 -i wg-hive -s 10.255.27.2 -d {subnet} -p tcp -m multiport --dports 8020,9870,9866,8030,8031,8032,8033,10020 -j ACCEPT
iptables -C DOCKER-USER -s 10.255.27.2 -d {subnet} -p tcp -m multiport --dports 8020,9870,9866,8030,8031,8032,8033,10020 -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER 1 -s 10.255.27.2 -d {subnet} -p tcp -m multiport --dports 8020,9870,9866,8030,8031,8032,8033,10020 -j ACCEPT
'''
# ApplicationMaster RPC ports are allocated dynamically inside the two NM containers.
for name in ['nodemanager1', 'nodemanager2']:
    ip = hosts[name]
    forward += f'iptables -t raw -C PREROUTING -i wg-hive -s 10.255.27.2 -d {ip} -p tcp --dport 1024:65535 -j ACCEPT 2>/dev/null || iptables -t raw -I PREROUTING 1 -i wg-hive -s 10.255.27.2 -d {ip} -p tcp --dport 1024:65535 -j ACCEPT\n'
    forward += f'iptables -C DOCKER-USER -i wg-hive -s 10.255.27.2 -d {ip} -p tcp --dport 1024:65535 -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER 1 -i wg-hive -s 10.255.27.2 -d {ip} -p tcp --dport 1024:65535 -j ACCEPT\n'
unit = '''[Unit]
Description=Allow Hive lab access to HDFS and YARN Docker network
After=docker.service
PartOf=docker.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/hive-hdfs-forward
[Install]
WantedBy=docker.service
'''
script = 'set -e\n'
script += f"sudo tee /usr/local/sbin/hive-hdfs-forward >/dev/null <<'EOF'\n{forward}EOF\n"
script += "sudo chmod 755 /usr/local/sbin/hive-hdfs-forward\n"
script += f"sudo tee /etc/systemd/system/hive-hdfs-forward.service >/dev/null <<'EOF'\n{unit}EOF\n"
script += 'sudo systemctl daemon-reload\nsudo systemctl enable hive-hdfs-forward\nsudo systemctl restart hive-hdfs-forward\n'
# Job JVMs need headroom on the 4 GiB NN. Keep this local swap across reboots.
script += '''if [ ! -f /swap-hive ]; then sudo fallocate -l 2G /swap-hive; sudo chmod 600 /swap-hive; sudo mkswap /swap-hive >/dev/null; fi
sudo swapon --show=NAME --noheadings | grep -qx /swap-hive || sudo swapon /swap-hive
grep -q '^/swap-hive ' /etc/fstab || echo '/swap-hive none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
'''
remote('team-27-nn', 'bash -s', script.encode())
# Hive LOAD DATA uses a proxy UGI even with HS2 doAs=false; grant only hive->hive.
proxy_script = """set -e
sudo python3 - <<'PYCFG'
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET
path = Path('/opt/hdfs-cluster-practical-1/config/core-site.xml')
backup = path.with_name('core-site.before-hive.xml.bak')
if not backup.exists(): shutil.copy2(path, backup)
tree = ET.parse(path); config = tree.getroot()
for name, value in {'hadoop.proxyuser.hive.hosts':'10.255.27.2','hadoop.proxyuser.hive.users':'hive'}.items():
    prop = next((p for p in config.findall('property') if p.findtext('name') == name), None)
    if prop is None:
        prop = ET.SubElement(config, 'property'); ET.SubElement(prop, 'name').text = name; ET.SubElement(prop, 'value')
    prop.find('value').text = value
tree.write(path, encoding='utf-8', xml_declaration=True)
PYCFG
sudo docker exec hdfs-lab-namenode-1 hdfs dfsadmin -refreshSuperUserGroupsConfiguration
sudo docker exec yarn-lab-resourcemanager-1 yarn rmadmin -refreshSuperUserGroupsConfiguration
"""
remote('team-27-nn', 'bash -s', proxy_script.encode())

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as tar:
    for f in root.rglob('*'):
        relative = f.relative_to(root)
        if f.is_file() and not any(x in {'.git', '.env', 'drivers', 'logs', '__pycache__', 'hive-site.xml', 'docker-compose.override.yml'} for x in relative.parts):
            tar.add(f, arcname=str(relative))
remote('team-27-00', 'sudo mkdir -p /opt/hive-cluster-practical-3 && sudo chown team:team /opt/hive-cluster-practical-3 && tar -xzf - -C /opt/hive-cluster-practical-3', buf.getvalue())

override = {'services': {service: {'extra_hosts': [f'{name}:{ip}' for name, ip in sorted(hosts.items())]} for service in ['metastore', 'hiveserver2']}}
route_unit = f'''[Unit]
Description=Route Hive node to existing HDFS Docker network
After=network-online.target wg-quick@wg-hive.service
Requires=wg-quick@wg-hive.service
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/ip route replace {subnet} dev wg-hive
[Install]
WantedBy=multi-user.target
'''
script = 'set -e\ncd /opt/hive-cluster-practical-3\n'
script += f"cat > docker-compose.override.yml <<'EOF'\n{json.dumps(override, indent=2)}\nEOF\n"
script += f"sudo tee /etc/systemd/system/hive-hdfs-route.service >/dev/null <<'EOF'\n{route_unit}EOF\n"
script += '''sudo systemctl daemon-reload
sudo systemctl enable hive-hdfs-route
sudo systemctl restart hive-hdfs-route
if ! command -v docker >/dev/null; then sudo apt-get update -qq; sudo apt-get install -y docker.io docker-compose-v2 curl; fi
sudo systemctl enable --now docker
chmod +x scripts/*.sh
sudo bash scripts/deploy.sh
'''
print(remote('team-27-00', 'bash -s', script.encode()).decode())
print('Deployment and data load completed')
