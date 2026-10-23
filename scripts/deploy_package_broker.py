"""Provision the separate package capability using setup credentials only."""
import json
from pathlib import Path
import subprocess
import shlex
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm/provisioning'))
import guest_setup
key=ROOT/'.local/credentials/installer_ed25519'
if not key.exists():subprocess.run(['ssh-keygen.exe','-q','-t','ed25519','-N','','-C','localpilot-installer','-f',str(key)],check=True)
host,options=guest_setup.connection()
source=ROOT/'.local/package_broker.py'
source.write_bytes((ROOT/'vm/provisioning/package_broker.py').read_bytes().replace(b'\r\n',b'\n'))
for path,name in ((source,'localpilot-package-broker.py'),(key.with_suffix('.pub'),'localpilot-installer.pub')):
    subprocess.run(['scp.exe',*options,str(path),'localpilot@'+host+':/home/localpilot/'+name],check=True)
sshd="Match User lp-installer\n    AuthorizedKeysFile /etc/ssh/authorized_keys/%u\n    AuthenticationMethods publickey\n    PasswordAuthentication no\n    KbdInteractiveAuthentication no\n    AllowTcpForwarding no\n    AllowStreamLocalForwarding no\n    PermitTTY no\n    X11Forwarding no\n    MaxSessions 1\n    ForceCommand /usr/bin/sudo -n /usr/bin/python3 /usr/local/lib/localpilot/package_broker.py\nMatch all\n"
sudoers='Defaults:lp-installer env_reset\nlp-installer ALL=(root) NOPASSWD: /usr/bin/python3 /usr/local/lib/localpilot/package_broker.py\n'
program="from pathlib import Path; key="+repr(key.with_suffix('.pub').read_text().strip())+"; p=Path('/etc/ssh/authorized_keys/lp-installer'); p.write_text('restrict '+key+'\\n'); p.chmod(0o644); Path('/etc/ssh/sshd_config.d/62-localpilot-installer.conf').write_text("+repr(sshd)+"); p=Path('/etc/sudoers.d/localpilot-installer'); p.write_text("+repr(sudoers)+"); p.chmod(0o440)"
install="set -e; install -d -o root -g root -m 755 /var/empty/localpilot-installer; if ! id lp-installer >/dev/null 2>&1; then useradd --system --no-create-home --home-dir /var/empty/localpilot-installer --shell /bin/sh lp-installer; usermod --password '*' lp-installer; fi; usermod --home /var/empty/localpilot-installer lp-installer; install -o root -g root -m 644 /home/localpilot/localpilot-package-broker.py /usr/local/lib/localpilot/package_broker.py; python3 -c "+shlex.quote(program)+"; /usr/sbin/visudo -cf /etc/sudoers.d/localpilot-installer; /usr/sbin/sshd -t; systemctl reload ssh"
guest_setup.ssh(install,privileged=True)
p=ROOT/'.local/runtime.json'
config=json.loads(p.read_text(encoding='utf-8'));config['installer_key']=str(key)
p.write_text(json.dumps(config,indent=2),encoding='utf-8')
print('Installed isolated package capability; pilot sudo permissions unchanged.')
