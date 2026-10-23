#!/usr/bin/env python3
"""Optional setup from included previous assignments; existing volumes are retained."""
import io
from pathlib import Path
import subprocess
import tarfile
from remote_lib import remote

ROOT=Path(__file__).resolve().parents[1]
for component,target in [('hdfs','/opt/hdfs-cluster-practical-1'),('yarn','/opt/yarn-cluster-practical-2')]:
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as tar:
        for path in (ROOT/'previous'/component).rglob('*'):
            if path.is_file():tar.add(path,arcname=str(path.relative_to(ROOT/'previous'/component)))
    remote('team-27-nn',f'sudo mkdir -p {target} && sudo chown team:team {target} && tar -xzf - -C {target}',buf.getvalue())
    script=f'''set -e
cd {target}
if ! command -v docker >/dev/null; then sudo apt-get update -qq; sudo apt-get install -y docker.io docker-compose-v2 curl python3; fi
sudo systemctl enable --now docker
chmod +x scripts/*.sh
sudo scripts/deploy.sh
'''
    print(remote('team-27-nn',script).decode(),flush=True)
subprocess.run(['python3',str(ROOT/'previous/hive/scripts/deploy-remote.py')],check=True)
print('Previous HDFS, YARN and Hive assignments deployed; now run scripts/deploy.py')
