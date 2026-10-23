"""SSH helpers: private keys remain on their original hosts."""
import shlex
import subprocess
from pathlib import Path

EDGE='team@2.59.81.216'
KEY=str(Path.home()/'.ssh/macbook_ed25519')
OPTIONS=['-o','BatchMode=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']

def remote(host, script, data=None):
    if host not in ['team-27-nn','team-27-00','team-27-01']:
        raise ValueError('Unknown host')
    command=shlex.join(['bash','-c',script])
    inner=['ssh','-i','.ssh/team_internal',*OPTIONS,'team@'+host,command]
    result=subprocess.run(['ssh','-i',KEY,*OPTIONS,EDGE,shlex.join(inner)],input=data,
                          stdout=subprocess.PIPE,check=True)
    return result.stdout
