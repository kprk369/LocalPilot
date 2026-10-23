#!/usr/bin/python3
"""Keep guest SSH limited to the current Windows Default Switch gateway."""
import ipaddress
import json
from pathlib import Path
import re
import subprocess

STATE = Path('/var/lib/localpilot/host-firewall.json')

def host_route(routes):
    for route in routes:
        gateway = ipaddress.ip_address(route.get('gateway', '0.0.0.0'))
        device = route.get('dev', '')
        private = any(gateway in net for net in (ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'), ipaddress.ip_network('192.168.0.0/16'))) if gateway.version == 4 else False
        if private and re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}', device):
            return {'gateway': str(gateway), 'device': device}
    raise RuntimeError('No private Windows gateway route available')

def rule(state):
    return ['allow', 'in', 'on', state['device'], 'from', state['gateway'], 'to', 'any', 'port', '22', 'proto', 'tcp', 'comment', 'LocalPilot Windows host']

def main():
    routes = json.loads(subprocess.check_output(['/usr/sbin/ip', '-j', '-4', 'route', 'show', 'default']))
    current = host_route(routes)
    try: previous = json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError): previous = None
    if previous == current:
        return
    subprocess.run(['/usr/sbin/ufw', *rule(current)], check=True)
    if previous:
        subprocess.run(['/usr/sbin/ufw', '--force', 'delete', *rule(previous)], check=True)
    # Remove the static bootstrap rule for this installation's current gateway.
    for address in {current['gateway']}:
        subprocess.run(['/usr/sbin/ufw', '--force', 'delete', 'allow', 'from', address, 'to', 'any', 'port', '22', 'proto', 'tcp'], check=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(current))
    temporary.replace(STATE)
    print('LocalPilot SSH firewall follows the current Windows gateway.')

if __name__ == '__main__': main()
