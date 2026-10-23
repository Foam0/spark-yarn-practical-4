#!/usr/bin/env python3
"""Provision native Spark client and a private route to the existing YARN cluster."""
import io
import json
from pathlib import Path
import shlex
import tarfile
from remote_lib import remote

ROOT=Path(__file__).resolve().parents[1]
containers=json.loads(remote('team-27-nn','sudo docker inspect $(sudo docker ps -q)'))
hosts={}
for c in containers:
    for net in c['NetworkSettings']['Networks'].values():
        for alias in net.get('Aliases') or []:
            if alias in ['namenode','datanode1','datanode2','datanode3','resourcemanager','historyserver','nodemanager1','nodemanager2']:
                hosts[alias]=net['IPAddress']
assert len(hosts)==8,hosts
subnet=json.loads(remote('team-27-nn','sudo docker network inspect hdfs-lab_hdfs'))[0]['IPAM']['Config'][0]['Subnet']
for host in ['team-27-nn','team-27-01']:
    remote(host,"""set -e
if ! command -v wg >/dev/null; then sudo apt-get update -qq; sudo apt-get install -y wireguard-tools >/dev/null; fi
sudo mkdir -p /etc/wireguard
if ! sudo test -s /etc/wireguard/spark.key; then sudo sh -c 'umask 077; wg genkey > /etc/wireguard/spark.key'; fi
""")
pubs={h:remote(h,"sudo sh -c 'wg pubkey < /etc/wireguard/spark.key'").decode().strip() for h in ['team-27-nn','team-27-01']}
for host,address,peer,endpoint,allowed in [
    ('team-27-nn','10.255.28.1/30','team-27-01','10.27.0.13:51828','10.255.28.2/32'),
    ('team-27-01','10.255.28.2/30','team-27-nn','10.27.0.11:51828',f'10.255.28.1/32,{subnet}')]:
    config=f'[Interface]\nAddress={address}\nListenPort=51828\nTable=off\nPrivateKey=PLACEHOLDER\n[Peer]\nPublicKey={pubs[peer]}\nEndpoint={endpoint}\nAllowedIPs={allowed}\nPersistentKeepalive=25\n'
    remote(host,f"""set -e
sudo tee /etc/wireguard/wg-spark.conf >/dev/null <<'EOF'
{config}EOF
sudo python3 -c "from pathlib import Path;p=Path('/etc/wireguard/wg-spark.conf');p.write_text(p.read_text().replace('PLACEHOLDER',Path('/etc/wireguard/spark.key').read_text().strip()));p.chmod(0o600)"
sudo systemctl enable wg-quick@wg-spark
sudo systemctl restart wg-quick@wg-spark
""")

ports='8020,9870,9866,8030,8031,8032,8033,10020'
fw='#!/bin/bash\nset -eu\n'
for table,chain in [('raw','PREROUTING'),('filter','DOCKER-USER')]:
    rule=f'-i wg-spark -s 10.255.28.2 -d {subnet} -p tcp -m multiport --dports {ports} -j ACCEPT'
    fw+=f'iptables -t {table} -C {chain} {rule} 2>/dev/null || iptables -t {table} -I {chain} 1 {rule}\n'
    for name in ['nodemanager1','nodemanager2']:
        rule=f'-i wg-spark -s 10.255.28.2 -d {hosts[name]} -p tcp --dport 1024:65535 -j ACCEPT'
        fw+=f'iptables -t {table} -C {chain} {rule} 2>/dev/null || iptables -t {table} -I {chain} 1 {rule}\n'
unit='''[Unit]
Description=Private Spark access to existing HDFS and YARN
After=docker.service wg-quick@wg-spark.service
Requires=docker.service wg-quick@wg-spark.service
PartOf=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/spark-yarn-forward
[Install]
WantedBy=docker.service
'''
remote('team-27-nn',f"""set -e
sudo tee /usr/local/sbin/spark-yarn-forward >/dev/null <<'EOF'
{fw}EOF
sudo chmod 755 /usr/local/sbin/spark-yarn-forward
sudo tee /etc/systemd/system/spark-yarn-forward.service >/dev/null <<'EOF'
{unit}EOF
sudo systemctl daemon-reload
sudo systemctl enable spark-yarn-forward
sudo systemctl restart spark-yarn-forward
""")

buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as tar:
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if path.is_file() and not any(p in {'.git','.venv','logs','__pycache__','runtime.json','generated-hosts','.env','hive-site.xml'} for p in rel.parts) and not path.name.endswith(('.key','.session')):
            tar.add(path,arcname=str(rel))
remote('team-27-01','sudo mkdir -p /opt/spark-yarn-practical-4 && sudo chown team:team /opt/spark-yarn-practical-4 && tar -xzf - -C /opt/spark-yarn-practical-4',buf.getvalue())
hostlines='\n'.join(f'{ip} {name}' for name,ip in sorted(hosts.items()))
route=f'''[Unit]
Description=Spark private route to existing HDFS Docker network
After=network-online.target wg-quick@wg-spark.service
Requires=wg-quick@wg-spark.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/ip route replace {subnet} dev wg-spark
[Install]
WantedBy=multi-user.target
'''
script=f"""set -e
cd /opt/spark-yarn-practical-4
sudo python3 - <<'PYHOST'
from pathlib import Path
p=Path('/etc/hosts')
s=p.read_text()
start='# BEGIN SPARK-LAB'; end='# END SPARK-LAB'
if start in s:s=s.split(start)[0]+s.split(end,1)[1]
p.write_text(s.rstrip()+'\\n'+start+'\\n'+{hostlines!r}+'\\n'+end+'\\n')
PYHOST
sudo tee /etc/systemd/system/spark-yarn-route.service >/dev/null <<'EOF'
{route}EOF
sudo systemctl daemon-reload
sudo systemctl enable spark-yarn-route
sudo systemctl restart spark-yarn-route
if ! test -x /usr/lib/jvm/java-17-openjdk-amd64/bin/java || ! test -x .venv/bin/python; then
  sudo apt-get update -qq
  sudo apt-get install -y openjdk-17-jre-headless python3-venv curl
fi
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
chmod +x scripts/*.sh
scripts/prepare-hdfs.sh
"""
print(remote('team-27-01',script).decode(),flush=True)
(ROOT/'logs').mkdir(exist_ok=True)
(ROOT/'logs/topology.json').write_text(json.dumps({'hosts':hosts,'subnet':subnet},indent=2))
print('DEPLOY PASS: native Spark client configured; existing HDFS input verified',flush=True)
