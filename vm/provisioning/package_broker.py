"""Root-owned fixed-operation package broker. No arbitrary commands or APT options."""
try:
    import fcntl
except ImportError:
    fcntl=None  # Pure plan validation is also tested on Windows.
import hashlib
import json
import os
import signal
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

CATALOG = {'tree', 'jq', 'ripgrep', 'firefox'}
ROOT = Path('/var/lib/localpilot/packages')
ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C','DEBIAN_FRONTEND':'noninteractive','NEEDRESTART_MODE':'l'}
APT = ['/usr/bin/apt-get','-o','DPkg::Lock::Timeout=60','-o','Acquire::Retries=1','-o','Acquire::http::Timeout=20','--no-install-recommends','--no-remove','--no-upgrade']

def digest(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def identifier(value):
    if not isinstance(value,str): raise ValueError('Invalid plan identifier')
    return str(uuid.UUID(value))

def write(path, value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,sort_keys=True))
    temp.chmod(0o600)
    temp.replace(path)

def load(plan_id):
    plan_id=identifier(plan_id)
    return json.loads((ROOT/(plan_id+'.json')).read_text())

def parse_actions(output):
    actions=[]
    configured=[]
    for line in output.splitlines():
        if line.startswith('Remv '):
            raise ValueError('Removal, upgrade, or unrelated configuration is not supported')
        if line.startswith('Conf '):
            configured.append(line.split()[1])
        if line.startswith('Inst '):
            match=re.fullmatch(r'Inst ([a-z0-9][a-z0-9+.:\-]*) \(([^\s()]+) .*\)',line)
            if not match: raise ValueError('Unsupported package operation: '+line[:200])
            name,version=match.groups()
            if not re.fullmatch(r'[A-Za-z0-9.+:~\-]+',version): raise ValueError('Invalid version')
            actions.append({'package':name,'version':version})
    if set(configured)-{item['package'] for item in actions}:raise ValueError('Unrelated package configuration is not supported')
    if len(actions)>40: raise ValueError('Installation plan exceeds package limit')
    return sorted(actions,key=lambda item:item['package'])

def simulate(packages):
    result=subprocess.run([*APT,'--simulate','install','--',*packages],env=ENV,capture_output=True,text=True,timeout=60)
    if result.returncode: raise ValueError('APT could not make a safe plan: '+result.stderr[-1500:])
    return parse_actions(result.stdout)

def verify_plan(record, expected_hash):
    plan=record['plan']
    if record['sha256']!=expected_hash or digest(plan)!=expected_hash: raise ValueError('Plan fingerprint mismatch')
    if record['status']!='planned': raise ValueError('Plan is already used')
    if time.time()>plan['expires']: raise ValueError('Plan expired; request a new plan')
    return plan

def read_status(plan_id):
    record=load(plan_id)
    if record['status'] in ('queued','installing') and record.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        record.update(status='interrupted',error='Guest restarted; inspect packages and request a new plan')
        write(ROOT/(identifier(plan_id)+'.json'),record)
    result={'ok':True,**record}
    log=ROOT/(identifier(plan_id)+'.log')
    if log.exists():
        with log.open('rb') as stream:
            stream.seek(max(0,log.stat().st_size-16000))
            result['output']=stream.read(16000).decode(errors='replace')
    return result

def dispatch(request):
    if not isinstance(request,dict) or set(request)-{'operation','packages','plan_id','sha256'}: raise ValueError('Invalid request fields')
    operation=request.get('operation')
    required={'plan':{'operation','packages'},'review':{'operation','plan_id'},'status':{'operation','plan_id'},'start':{'operation','plan_id','sha256'}}
    if operation not in required or set(request)!=required[operation]: raise ValueError('Unknown or malformed operation')
    if operation=='plan':
        packages=request['packages']
        if not isinstance(packages,list) or not 1<=len(packages)<=3 or any(not isinstance(name,str) or name not in CATALOG for name in packages) or len(set(packages))!=len(packages):
            raise ValueError('Choose unique packages only from tree, jq, ripgrep, firefox')
        plan_id=str(uuid.uuid4())
        plan={'id':plan_id,'requested':sorted(packages),'actions':simulate(sorted(packages)),'expires':int(time.time())+600,'scope':'Ubuntu VM only; new packages; no removal or upgrade'}
        record={'plan':plan,'sha256':digest(plan),'status':'planned'}
        write(ROOT/(plan_id+'.json'),record)
        return {'ok':True,**record}
    plan_id=identifier(request['plan_id'])
    if operation in ('review','status'):return read_status(plan_id)
    with (ROOT/'accept.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        active=ROOT/'active.json'
        if active.exists():
            previous=read_status(json.loads(active.read_text())['id'])
            if previous['status'] in ('queued','installing'):raise ValueError('Another package installation is still running')
        record=load(plan_id)
        plan=verify_plan(record,request['sha256'])
        record.update(status='queued',boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        write(ROOT/(plan_id+'.json'),record)
        write(active,{'id':plan_id})
        try:
            subprocess.run(['/usr/bin/systemd-run','--quiet','--collect','--service-type=exec','--unit=localpilot-install-'+plan_id,'/usr/bin/python3',str(Path(__file__).resolve()),'--worker',plan_id],check=True,env=ENV,capture_output=True,timeout=15)
        except Exception:
            record.update(status='failed',error='Could not start installation worker')
            write(ROOT/(plan_id+'.json'),record)
            raise
    return {'ok':True,'plan_id':plan_id,'status':'queued','message':'Installation runs independently so disconnect or task cancellation cannot interrupt dpkg.'}

def worker(plan_id):
    plan_id=identifier(plan_id)
    path=ROOT/(plan_id+'.json')
    record=load(plan_id)
    if record['status']!='queued' or digest(record['plan'])!=record['sha256']:raise ValueError('Invalid queued job')
    with (ROOT/'install.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            record['status']='installing';write(path,record)
            actions=record['plan']['actions']
            pinned=[item['package']+'='+item['version'] for item in actions]
            if actions:
                if simulate(pinned)!=actions:raise ValueError('Package state changed; request a new plan')
                with (ROOT/(plan_id+'.log')).open('wb') as output:
                    process=subprocess.run([*APT,'--assume-yes','install','--',*pinned],env=ENV,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
                    if process.returncode:raise ValueError('APT failed; inspect output before retrying')
            versions={}
            for name in record['plan']['requested']:
                result=subprocess.run(['/usr/bin/dpkg-query','-W','-f=${Status} ${Version}',name],env=ENV,capture_output=True,text=True,check=True)
                if not result.stdout.startswith('install ok installed '):raise ValueError('Package installation not verified')
                versions[name]=result.stdout.removeprefix('install ok installed ').strip()
            record.update(status='completed',installed=versions)
        except Exception as error:
            record.update(status='failed',error=str(error))
        write(path,record)

def main():
    if os.geteuid()!=0:raise PermissionError('Broker requires its dedicated privileged channel')
    signal.signal(signal.SIGHUP,signal.SIG_IGN)
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':return worker(sys.argv[2])
    if len(sys.argv)!=1:raise ValueError('Command line arguments are not supported')
    try:
        raw=sys.stdin.buffer.read(8193)
        if len(raw)>8192:raise ValueError('Request too large')
        result=dispatch(json.loads(raw))
    except Exception as error:result={'ok':False,'error':type(error).__name__+': '+str(error)}
    print(json.dumps(result))

if __name__=='__main__':main()
