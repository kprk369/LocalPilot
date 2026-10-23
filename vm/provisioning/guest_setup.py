"""Bootstrap the newly-created LocalPilot guest over key-authenticated SSH.
Never prints generated passwords. Uses a dedicated known-hosts file.
"""
import argparse, ipaddress, json, subprocess, shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'.local'

def connection():
    state=json.loads((LOCAL/'network-status.json').read_text(encoding='utf-8-sig'))
    created=json.loads((LOCAL/'vm-created.json').read_text(encoding='utf-8-sig'))
    if state['VMId'] != created['Id']:
        raise SystemExit('VM identity mismatch.')
    discovery=Path('C:/ProgramData/LocalPilot/network.json')
    if discovery.exists():
        discovered=json.loads(discovery.read_text(encoding='utf-8-sig'))
        if discovered.get('VMId')==created['Id'] and discovered.get('State')=='Running':
            state=discovered
    addresses=[ipaddress.ip_address(x) for x in state['IPs']]
    addresses=[str(x) for x in addresses if x.version==4 and x.is_private and not x.is_loopback]
    if not addresses:
        raise SystemExit('No private LocalPilot VM address is available yet.')
    options=['-i',str(LOCAL/'credentials/admin_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={LOCAL / "credentials/known_hosts"}']
    known=LOCAL/'credentials/known_hosts'
    if known.exists() and any(line.startswith('localpilot-vm ') for line in known.read_text().splitlines()):
        options=[value.replace('StrictHostKeyChecking=accept-new','StrictHostKeyChecking=yes') for value in options]
        options.extend(['-o','HostKeyAlias=localpilot-vm'])
    cache=LOCAL/'credentials/guest-address.json'
    if cache.exists():
        cached=json.loads(cache.read_text())
        if cached.get('VMId')==state['VMId'] and cached.get('IP') in addresses:
            return cached['IP'],options
    for host in addresses:
        probe=subprocess.run(['ssh.exe',*options,f'localpilot@{host}','test -f /etc/localpilot/bootstrap-complete && hostname'],capture_output=True,text=True)
        if probe.returncode==0 and probe.stdout.strip()=='localpilot':
            cache.write_text(json.dumps({'VMId':state['VMId'],'IP':host}))
            return host,options
    raise SystemExit('The installed LocalPilot system is not accepting its bootstrap SSH key yet.')

def ssh(command, *, privileged=False, log=None):
    host, options=connection()
    data=None
    if privileged:
        password=json.loads((LOCAL/'credentials/bootstrap.json').read_text())['admin_password']
        command="sudo -S -p '' bash -c "+shlex.quote(command)
        data=(password+'\n').encode()
    result=subprocess.run(['ssh.exe',*options,f'localpilot@{host}',command],input=data,stdout=log,stderr=subprocess.STDOUT if log else None)
    if result.returncode:
        raise SystemExit(f'Guest command failed with exit code {result.returncode}.')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['check','provision','tailscale-login','tailscale-status','serve','desktop-health'])
    args=parser.parse_args()
    if args.action=='check':
        ssh('hostname; id pilot; systemctl is-active ssh xrdp; test -f /etc/localpilot/bootstrap-complete')
    elif args.action=='provision':
        host, options=connection()
        data=json.loads((LOCAL/'credentials/bootstrap.json').read_text())
        data.setdefault('guacamole_password',__import__('secrets').token_urlsafe(24))
        (LOCAL/'credentials/bootstrap.json').write_text(json.dumps(data,indent=2))
        guest_data={'desktop_password':data['desktop_password'],'guacamole_password':data['guacamole_password']}
        transfer=LOCAL/'credentials/guest-bootstrap.json'
        transfer.write_text(json.dumps(guest_data))
        script=LOCAL/'provision-desktop.sh'
        script.write_bytes((ROOT/'vm/provisioning/provision-desktop.sh').read_bytes().replace(b'\r\n',b'\n'))
        for source,target in [(transfer,'localpilot-bootstrap.json'),(script,'provision-desktop.sh')]:
            subprocess.run(['scp.exe',*options,str(source),f'localpilot@{host}:/home/localpilot/{target}'],check=True)
        ssh('chmod 600 /home/localpilot/localpilot-bootstrap.json /home/localpilot/provision-desktop.sh')
        with (LOCAL/'logs/desktop-provision.log').open('a') as log:
            ssh('bash /home/localpilot/provision-desktop.sh',privileged=True,log=log)
        sys=__import__('sys')
        sys.path.insert(0,str(ROOT/'scripts'))
        from network_recovery_payload import payload
        ssh('python3 -c '+shlex.quote(payload()),privileged=True)
        print('Desktop gateway provisioning completed. See .local/logs/desktop-provision.log.')
    elif args.action=='tailscale-login':
        ssh('tailscale up --timeout=90s',privileged=True)
    elif args.action=='tailscale-status':
        ssh('tailscale status --json',privileged=True)
    elif args.action=='serve':
        ssh('tailscale serve --bg http://127.0.0.1:8080',privileged=True)
    else:
        ssh('systemctl is-active xrdp tailscaled; docker compose -f /opt/localpilot/compose.json ps; curl --fail --silent --output /dev/null --write-out "Guacamole HTTP %{http_code}\\n" http://127.0.0.1:8080/guacamole/',privileged=True)

if __name__=='__main__':main()
