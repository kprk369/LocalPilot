"""Read-only diagnostics for the existing LocalPilot installation.

Run: .venv\\Scripts\\python.exe -m scripts.doctor
No provisioning, service restart, model loading, or task replay is performed.
"""
import asyncio
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import time
import httpx
from backend.config import Settings,ROOT

async def main():
    checks={}
    try:settings=Settings.load()
    except Exception as error:
        print(json.dumps({'ready':False,'configuration':type(error).__name__,'action':'Check private runtime configuration; do not regenerate credentials.'},indent=2));return 1
    checks['private_files']={'ok':all(Path(p).is_file() for p in [settings.ssh_key,settings.known_hosts,settings.installer_key]),'host_key_pinned':settings.host_key_alias=='localpilot-vm'}
    checks['private_files']['ok'] &= checks['private_files']['host_key_pinned']
    async with httpx.AsyncClient(trust_env=False,timeout=15) as client:
        headers={'Authorization':'Bearer '+settings.token}
        for name,route in [('backend','health'),('linux','linux/status'),('control','desktop/state')]:
            try:
                r=await client.get('http://127.0.0.1:8765/'+route,headers=headers);r.raise_for_status();value=r.json()
                ok={'backend':value.get('status')=='ok','linux':value.get('state')=='ready','control':bool(value.get('confirmed'))}[name]
                checks[name]={'ok':ok,'detail':value}
            except Exception as error:checks[name]={'ok':False,'error':type(error).__name__}
        try:
            r=await client.get(settings.ollama_url+'/api/tags');r.raise_for_status()
            model=next((m for m in r.json()['models'] if m.get('name')==settings.model),None)
            size=model.get('details',{}).get('parameter_size','') if model else ''
            checks['model']={'ok':bool(model) and size.startswith('27'),'tag':settings.model,'parameter_size':size,'note':'Installed-model check only; does not load it or measure inference.'}
        except Exception as error:checks['model']={'ok':False,'error':type(error).__name__}
    try:
        with sqlite3.connect(Path(settings.database).resolve().as_uri()+'?mode=ro',uri=True) as db:
            integrity=db.execute('PRAGMA quick_check').fetchone()[0]
            active=db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('queued','running','paused','awaiting_approval')").fetchone()[0]
            total=db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        checks['history']={'ok':integrity=='ok','tasks':total,'active_tasks':active}
    except Exception as error:checks['history']={'ok':False,'error':type(error).__name__}
    try:
        state=json.loads((ROOT/'.local/service-status.json').read_text(encoding='utf-8'))
        age=round(time.time()-state['time'],1)
        checks['supervisor']={'ok':0<=age<45 and state.get('backend_ready',False) and state.get('ollama_ready',False),'last_check_age_seconds':age}
    except Exception as error:checks['supervisor']={'ok':False,'error':type(error).__name__}
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'ready':all(c['ok'] for c in checks.values()),'checks':checks,
            'limits':'Does not test iPhone/Tailscale reachability, website availability, or execute a task. Human ownership can be healthy; Resume AI before assigning work.'}
    print(json.dumps(result,indent=2))
    return 0 if result['ready'] else 1

if __name__=='__main__':raise SystemExit(asyncio.run(main()))
