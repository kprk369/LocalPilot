"""Maintain a forwarding-only transport; follow pinned VM address changes."""
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.network import resolve_host
from scripts.runtime_support import CREATE_NO_WINDOW, single_instance, stop_child

def main():
    mutex = single_instance('LocalPilotGateway')
    if mutex is None:
        return
    process = None
    try:
        while not (ROOT / '.local/stop-services').exists():
            config = json.loads((ROOT / '.local/gateway.json').read_text(encoding='utf-8'))
            alias = config.get('host_key_alias', '')
            host = resolve_host(config['host'], alias)
            command = ['ssh.exe', '-N', '-T', '-i', config['key'], '-o', 'BatchMode=yes',
                       '-o', 'StrictHostKeyChecking=yes', '-o', f"UserKnownHostsFile={config['known_hosts']}",
                       '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=10',
                       '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
            if alias: command += ['-o', 'HostKeyAlias=' + alias]
            command += ['-R', '127.0.0.1:18765:127.0.0.1:8765', 'lp-gateway@' + host]
            print('Connecting private LocalPilot transport...', flush=True)
            process = subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)
            while process.poll() is None:
                time.sleep(5)
                if (ROOT / '.local/stop-services').exists() or resolve_host(config['host'], alias) != host:
                    stop_child(process)
                    break
            print('Transport disconnected; retrying in five seconds.', flush=True)
            time.sleep(5)
    finally:
        stop_child(process)

if __name__ == '__main__':
    main()
