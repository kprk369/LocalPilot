"""Run LocalPilot as the signed-in user, with bounded logs and crash recovery."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.network import resolve_host
from scripts.runtime_support import CREATE_NO_WINDOW, port_open, single_instance, stop_child
LOGS = ROOT / '.local/logs'

def api_get(route, config):
    request = urllib.request.Request('http://127.0.0.1:8765/' + route,
                                    headers={'Authorization': 'Bearer ' + config['token']})
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.load(response)

def launch(arguments, name):
    path = LOGS / (name + '.log')
    if path.exists() and path.stat().st_size > 2_000_000:
        path.replace(LOGS / (name + '.previous.log'))
    with path.open('ab') as stream:
        return subprocess.Popen(arguments, cwd=ROOT, stdout=stream, stderr=stream,
                                creationflags=CREATE_NO_WINDOW)

def main():
    mutex = single_instance('LocalPilotSupervisor')
    if mutex is None:
        return
    LOGS.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOGS / 'supervisor.log', maxBytes=1_000_000, backupCount=2)
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(message)s')
    stop = ROOT / '.local/stop-services'
    children = {'backend': None, 'gateway': None, 'ollama': None}
    failures = 0
    last_ollama_start = 0
    python = str(ROOT / '.venv/Scripts/python.exe')
    (ROOT / '.local/supervisor.pid').write_text(str(os.getpid()), encoding='ascii')
    logging.info('LocalPilot supervision started as the signed-in user.')
    try:
        while not stop.exists():
            try:
                config = json.loads((ROOT / '.local/runtime.json').read_text(encoding='utf-8'))
                if not port_open(11434) and time.monotonic() - last_ollama_start > 60:
                    ollama = Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe'
                    if ollama.exists() and (children['ollama'] is None or children['ollama'].poll() is not None):
                        children['ollama'] = launch([str(ollama), 'serve'], 'ollama-recovery')
                        last_ollama_start = time.monotonic()
                        logging.info('Started local Ollama recovery process.')
                backend = children['backend']
                if not port_open(8765):
                    if backend is None or backend.poll() is not None:
                        children['backend'] = launch([python, '-m', 'uvicorn', 'backend.main:app', '--host',
                            '127.0.0.1', '--port', '8765', '--no-access-log'], 'backend-service')
                        failures = 0
                        logging.info('Started LocalPilot backend.')
                else:
                    try:
                        health = api_get('health', config)
                        if health.get('status') != 'ok': raise ValueError('Unexpected backend status')
                        failures = 0
                        # Repair failed initial ownership discovery once the guest becomes reachable.
                        state = api_get('desktop/state', config)
                        if not state.get('confirmed'):
                            request = urllib.request.Request('http://127.0.0.1:8765/desktop/control',
                                data=b'{"owner":"human"}', method='POST', headers={
                                'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
                            try:
                                with urllib.request.urlopen(request, timeout=15): pass
                            except Exception: pass
                    except Exception:
                        failures += 1
                        if failures >= 6 and backend is not None and backend.poll() is None:
                            logging.warning('Owned backend unresponsive; restarting after repeated health failures.')
                            stop_child(backend)
                            children['backend'] = None
                            failures = 0
                gateway = children['gateway']
                if gateway is None or gateway.poll() is not None:
                    children['gateway'] = launch([python, '-u', str(ROOT / 'scripts/gateway_tunnel.py')], 'gateway-service')
                    logging.info('Started private transport worker.')
                status = {'time': time.time(), 'backend_ready': port_open(8765),
                          'ollama_ready': port_open(11434),
                          'vm_host': resolve_host(config['ssh_host'], config.get('host_key_alias', '')),
                          'supervisor_pid': os.getpid()}
                (ROOT / '.local/service-status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
            except Exception:
                logging.exception('Service check failed; retrying.')
            time.sleep(10)
    finally:
        for process in children.values(): stop_child(process)
        logging.info('LocalPilot supervision stopped.')

if __name__ == '__main__':
    main()
