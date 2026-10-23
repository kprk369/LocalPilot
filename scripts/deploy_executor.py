"""Install the pilot-only dispatcher using setup credentials, never runtime credentials."""
import json, secrets, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm/provisioning'))
import guest_setup
local=ROOT/'.local'
key=local/'credentials/agent_ed25519'
if not key.exists():
    subprocess.run(['ssh-keygen.exe','-q','-t','ed25519','-N','','-C','localpilot-agent','-f',str(key)],check=True)
host,options=guest_setup.connection()
public=key.with_suffix('.pub')
normalized=local/'executor.py'
normalized.write_bytes((ROOT/'vm/provisioning/executor.py').read_bytes().replace(b'\r\n',b'\n'))
desktop=local/'desktop_tools.py'
desktop.write_bytes((ROOT/'vm/provisioning/desktop_tools.py').read_bytes().replace(b'\r\n',b'\n'))
browser=local/'browser_tools.py'
browser.write_bytes((ROOT/'vm/provisioning/browser_tools.py').read_bytes().replace(b'\r\n',b'\n'))
routine=local/'routine_commands.py'
routine.write_bytes((ROOT/'vm/provisioning/routine_commands.py').read_bytes().replace(b'\r\n',b'\n'))
for source,name in [(routine,'localpilot-routine-commands.py'),(browser,'localpilot-browser-tools.py'),(normalized,'localpilot-executor.py'),(desktop,'localpilot-desktop-tools.py'),(public,'localpilot-agent.pub')]:
    subprocess.run(['scp.exe',*options,str(source),f'localpilot@{host}:/home/localpilot/{name}'],check=True)
command='''set -e
install -d -m 755 /etc/ssh/authorized_keys /usr/local/lib/localpilot
install -o root -g root -m 644 /home/localpilot/localpilot-routine-commands.py /usr/local/lib/localpilot/routine_commands.py
install -o root -g root -m 644 /home/localpilot/localpilot-executor.py /usr/local/lib/localpilot/executor.py
install -o root -g root -m 644 /home/localpilot/localpilot-desktop-tools.py /usr/local/lib/localpilot/desktop_tools.py
install -o root -g root -m 644 /home/localpilot/localpilot-browser-tools.py /usr/local/lib/localpilot/browser_tools.py
python3 - <<'PY'
from pathlib import Path
key=Path('/home/localpilot/localpilot-agent.pub').read_text().strip()
if not key.startswith('ssh-ed25519 ') or '\\n' in key:
    raise ValueError('Unexpected public key')
Path('/etc/ssh/authorized_keys/pilot').write_text('restrict '+key+'\\n')
Path('/etc/ssh/authorized_keys/pilot').chmod(0o644)
Path('/etc/ssh/sshd_config.d/60-localpilot-pilot.conf').write_text(''' + repr('Match User pilot\n    AuthorizedKeysFile /etc/ssh/authorized_keys/%u\n    PasswordAuthentication no\n    KbdInteractiveAuthentication no\n    AllowTcpForwarding no\n    PermitTTY no\n    X11Forwarding no\n    ForceCommand /usr/bin/python3 /usr/local/lib/localpilot/executor.py\nMatch all\n') + ''')
PY
/usr/sbin/sshd -t
systemctl reload ssh
id pilot
'''
guest_setup.ssh(command,privileged=True)
config_path=local/'runtime.json'
config=json.loads(config_path.read_text()) if config_path.exists() else {'token':secrets.token_urlsafe(32)}
config.update({'ssh_host':host,'ssh_key':str(key),'known_hosts':str(local/'credentials/known_hosts'),'model':'qwen3.8:latest','ollama_url':'http://127.0.0.1:11434','database':str(local/'tasks.sqlite3')})
config_path.write_text(json.dumps(config,indent=2))
print('Installed root-owned dispatcher and pilot-only SSH rules. Runtime configuration saved privately.')
