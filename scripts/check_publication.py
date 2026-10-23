"""Check the Git publication set without displaying secret values.

Run python -m scripts.check_publication [--archive]. Archive output stays under
ignored .local/releases. No commit, remote creation, or upload is performed.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
import zipfile
from backend.config import ROOT

PUBLIC_DIRS={'backend','frontend','scripts','tests','vm','docs','config','.github'}
PUBLIC_FILES={'.gitignore','.gitattributes','README.md','CONTRIBUTING.md','SECURITY.md','LICENSE','pyproject.toml','requirements.txt','requirements-dev.txt'}
PATTERNS={
 'private-key header':re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----'),
 'GitHub token':re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})'),
 'provider token':re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}'),
}


def candidates():
    top=subprocess.run(['git','-C',str(ROOT),'rev-parse','--show-toplevel'],capture_output=True,text=True,check=True).stdout.strip()
    if Path(top).resolve()!=ROOT.resolve():raise RuntimeError('Run publication checks from this project Git root')
    result=subprocess.run(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z'],capture_output=True,check=True)
    return sorted(set(result.stdout.decode('utf-8').split('\0'))-{''})


def known_private_values():
    values=set()
    for file in [ROOT/'.local/runtime.json',ROOT/'.local/credentials/bootstrap.json',ROOT/'.local/credentials/guest-bootstrap.json']:
        if not file.exists():continue
        data=json.loads(file.read_text(encoding='utf-8-sig'))
        for key,value in data.items():
            if isinstance(value,str) and len(value)>=12 and (key=='token' or 'password' in key):values.add(value.encode())
        if data.get('public_origin'):
            host=urlparse(data['public_origin']).hostname
            if host:values.add(host.encode())
    file=ROOT/'.local/vm-created.json'
    if file.exists():
        value=json.loads(file.read_text(encoding='utf-8-sig')).get('Id','')
        if value:values.add(value.encode())
    return values


def inspect_files(files,private_values=()):
    findings=[];total=0
    for name in files:
        path=ROOT/name;relative=Path(name)
        if relative.parts[0] not in PUBLIC_DIRS and name not in PUBLIC_FILES:
            findings.append({'file':name,'reason':'outside explicit public source allowlist'});continue
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            findings.append({'file':name,'reason':'linked or escaping source path'});continue
        if not path.is_file():findings.append({'file':name,'reason':'not a regular file'});continue
        if any(part in {'.local','.venv','.git','__pycache__','credentials','.pytest_cache'} for part in relative.parts):
            findings.append({'file':name,'reason':'private/generated directory'});continue
        if path.stat().st_size>2*1024*1024:
            findings.append({'file':name,'reason':'unexpected large source file'});continue
        content=path.read_bytes();total+=len(content)
        for label,pattern in PATTERNS.items():
            if pattern.search(content):findings.append({'file':name,'reason':label})
        if any(value in content for value in private_values):findings.append({'file':name,'reason':'matches a known private installation value'})
        if re.search(rb'(?:C:[\\/]+Users[\\/]+|C:Users)[A-Za-z0-9_.-]+',content,re.I):
            findings.append({'file':name,'reason':'personal Windows profile path'})
    return {'passed':not findings,'file_count':len(files),'total_bytes':total,'findings':findings}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',action='store_true');args=parser.parse_args()
    files=candidates()
    if not files or 'README.md' not in files:raise RuntimeError('No valid source publication set found')
    result=inspect_files(files,known_private_values())
    if args.archive and result['passed']:
        directory=ROOT/'.local/releases';directory.mkdir(parents=True,exist_ok=True)
        path=directory/('localpilot-source-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.zip')
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:archive.write(ROOT/name,name)
        with zipfile.ZipFile(path) as archive:
            if sorted(archive.namelist())!=files or archive.testzip() is not None:raise RuntimeError('Source archive verification failed')
        result.update(archive=str(path),archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        (directory/'latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
