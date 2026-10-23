"""Provision a forwarding-only identity; no setup key is used by the tunnel."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm/provisioning'))
import guest_setup
local=ROOT/'.local';key=local/'credentials/gateway_ed25519'
if not key.exists():subprocess.run(['ssh-keygen.exe','-q','-t','ed25519','-N','','-C','localpilot-web-transport','-f',str(key)],check=True)
host,options=guest_setup.connection()
script=local/'provision-web-gateway.sh'
script.write_bytes((ROOT/'vm/provisioning/provision-web-gateway.sh').read_bytes().replace(b'\r\n',b'\n'))
for source,target in [(key.with_suffix('.pub'),'localpilot-gateway.pub'),(script,'provision-web-gateway.sh')]:
 subprocess.run(['scp.exe',*options,str(source),f'localpilot@{host}:/home/localpilot/{target}'],check=True)
with (local/'logs/web-gateway-setup.log').open('a') as log:
 guest_setup.ssh('bash /home/localpilot/provision-web-gateway.sh',privileged=True,log=log)
(local/'gateway.json').write_text(json.dumps({'host':host,'key':str(key),'known_hosts':str(local/'credentials/known_hosts')},indent=2))
print('Dedicated forwarding-only gateway configured. Existing desktop route preserved.')
