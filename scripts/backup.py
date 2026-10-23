"""Private, manual LocalPilot backups and non-destructive staged restore.

Use python -m scripts.backup create | verify PATH | restore PATH DESTINATION.
The destination must not exist. No live configuration or VM state is replaced.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import uuid
from backend.network import provisioned_vm_id
import httpx
from backend.config import ROOT, Settings

MAX_BYTES=1024**3
MAX_MEMBERS=100000



def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def safe_member(name):
    path=PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or '..' in path.parts or ':' in name:
        raise ValueError('Unsafe backup member path')
    return path


def safe_windows_member(name):
    path=safe_member(name)
    for part in path.parts:
        if part.endswith((' ','.')) or PureWindowsPath(part).is_reserved() or any(ord(c)<32 or c in '<>"|?*' for c in part):
            raise ValueError('Workspace name cannot be safely restored on Windows; keep the Linux archive')
    return path


def private_directory(path):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=False)
    if os.name=='nt':
        code=r"""$ErrorActionPreference='Stop'
$p=$env:LOCALPILOT_PRIVATE_DIR
$acl=New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
foreach($sid in @($user,(New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')))){
 $rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $p -AclObject $acl
"""
        result=subprocess.run([shutil.which('pwsh.exe') or 'powershell.exe','-NoProfile','-NonInteractive','-Command',code],env={**os.environ,'LOCALPILOT_PRIVATE_DIR':str(path)},capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Could not restrict backup directory permissions')
    else:path.chmod(0o700)
    return path


def idle(settings):
    with httpx.Client(base_url='http://127.0.0.1:8765',headers={'Authorization':'Bearer '+settings.token},trust_env=False,timeout=15) as client:
        response=client.get('/tasks');response.raise_for_status()
        if any(t['status'] in ('queued','running','paused','awaiting_approval') for t in response.json()):
            raise RuntimeError('Finish or cancel active tasks before creating a backup')


# Run as pilot through the setup channel; this does not expand runtime tools.
EXPORT=r"""
import hashlib,io,json,os,stat,sys,tarfile
from pathlib import Path
root=Path('/home/pilot/Workspace')
if root.is_symlink() or not root.is_dir():raise RuntimeError('Workspace must be a real directory')
entries=[];omitted=[];total=0
for base,dirs,files in os.walk(root,followlinks=False):
 for name in list(dirs):
  p=Path(base)/name
  if p.is_symlink():omitted.append({'path':p.relative_to(root).as_posix(),'reason':'symlink'});dirs.remove(name)
 for name in dirs+files:
  p=Path(base)/name;info=p.lstat();rel=p.relative_to(root).as_posix()
  if stat.S_ISLNK(info.st_mode):omitted.append({'path':rel,'reason':'symlink'});continue
  if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
   omitted.append({'path':rel,'reason':'special file'});continue
  if stat.S_ISREG(info.st_mode):
   total+=info.st_size
   if total>1024**3 or info.st_size>256*1024**2:raise RuntimeError('Workspace exceeds backup size allowance')
  entries.append((p,info))
  if len(entries)>100000:raise RuntimeError('Too many workspace entries')
manifest={'files':{},'omitted':omitted,'consistency':'Per-file stability checks; not a VM snapshot'}
class HashReader:
 def __init__(self,stream):self.stream=stream;self.hash=hashlib.sha256()
 def read(self,size=-1):
  data=self.stream.read(size);self.hash.update(data);return data
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz',format=tarfile.PAX_FORMAT) as archive:
 for p,before in entries:
  rel=p.relative_to(root).as_posix();item=tarfile.TarInfo('workspace/'+rel)
  item.mode=stat.S_IMODE(before.st_mode);item.mtime=before.st_mtime
  if stat.S_ISDIR(before.st_mode):item.type=tarfile.DIRTYPE;archive.addfile(item);continue
  # O_NOFOLLOW prevents a file replaced by a symlink from escaping the workspace.
  fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as stream:
   current=os.fstat(stream.fileno())
   if (current.st_ino,current.st_size,current.st_mtime_ns)!=(before.st_ino,before.st_size,before.st_mtime_ns):raise RuntimeError('Workspace changed during backup')
   item.size=before.st_size;reader=HashReader(stream);archive.addfile(item,reader)
   after=os.fstat(stream.fileno())
   if (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns):raise RuntimeError('Workspace changed during backup')
   manifest['files'][rel]={'bytes':item.size,'sha256':reader.hash.hexdigest()}
 data=json.dumps(manifest).encode();item=tarfile.TarInfo('workspace-manifest.json');item.size=len(data);item.mode=0o600;archive.addfile(item,io.BytesIO(data))
"""


def workspace_export(destination):
    from vm.provisioning import guest_setup
    host,options=guest_setup.connection()
    # The current setup must retain its pinned known-host identity.
    if 'HostKeyAlias=localpilot-vm' not in options or 'StrictHostKeyChecking=yes' not in options:
        raise RuntimeError('Pinned VM host key is required for backup')
    password=json.loads((ROOT/'.local/credentials/bootstrap.json').read_text(encoding='utf-8'))['admin_password']
    command="sudo -S -p '' -u pilot python3 -c "+shlex.quote(EXPORT)
    with destination.open('xb') as output:
        result=subprocess.run(['ssh.exe',*options,'localpilot@'+host,command],input=(password+'\n').encode(),stdout=output,stderr=subprocess.PIPE,timeout=180)
    if result.returncode:raise RuntimeError('Linux workspace export failed; partial backup is not complete')


def verify_workspace(path):
    actual={};seen=set();manifest=None;total=0
    with tarfile.open(path,'r:gz') as archive:
        for index,member in enumerate(archive):
            if index>=MAX_MEMBERS:raise ValueError('Too many archive entries')
            name=safe_member(member.name).as_posix()
            if name in seen:raise ValueError('Duplicate workspace member')
            seen.add(name)
            if not (member.isfile() or member.isdir()):raise ValueError('Links and special files are forbidden')
            if name!='workspace-manifest.json' and not name.startswith('workspace/'):
                raise ValueError('Unexpected workspace archive path')
            if member.isdir():continue
            total+=member.size
            if total>MAX_BYTES+16*1024**2:raise ValueError('Workspace archive exceeds size limit')
            stream=archive.extractfile(member)
            if name=='workspace-manifest.json':
                if member.size>16*1024**2:raise ValueError('Workspace manifest too large')
                manifest=json.load(stream)
            else:
                h=hashlib.sha256();count=0
                for chunk in iter(lambda:stream.read(1024*1024),b''):count+=len(chunk);h.update(chunk)
                actual[name[len('workspace/'):]]={'bytes':count,'sha256':h.hexdigest()}
    if not isinstance(manifest,dict) or actual!=manifest.get('files'):raise ValueError('Workspace hashes do not match')
    return {'files':len(actual),'bytes':sum(v['bytes'] for v in actual.values()),'omitted':manifest.get('omitted',[])}


def copy_file(source,destination):
    if source.is_symlink() or not source.is_file():raise ValueError('Expected a regular source file')
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination)


def create():
    settings=Settings.load();idle(settings)
    vm_id=provisioned_vm_id()
    if not vm_id:raise RuntimeError('Valid private LocalPilot VM identity is required')
    base=ROOT/'.local/backups';base.mkdir(exist_ok=True)
    target=private_directory(base/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]))
    # No success marker is written until every component verifies.
    for name in ['backend','frontend','scripts','tests','vm','docs']:
        for source in (ROOT/name).rglob('*'):
            if '__pycache__' in source.parts or source.suffix=='.pyc':continue
            if source.is_symlink():raise ValueError('Source tree symlink is not supported')
            if source.is_file():copy_file(source,target/'project'/source.relative_to(ROOT))
    for name in ['README.md','requirements.txt','requirements-dev.txt','pyproject.toml','.gitignore']:
        copy_file(ROOT/name,target/'project'/name)
    for name in ['runtime.json','gateway.json','vm-created.json','network-status.json','startup-installed.json']:
        copy_file(ROOT/'.local'/name,target/'private'/name)
    for source in (ROOT/'.local/credentials').iterdir():
        copy_file(source,target/'private/credentials'/source.name)
    dbpath=target/'private/tasks.sqlite3'
    with sqlite3.connect(Path(settings.database).resolve().as_uri()+'?mode=ro',uri=True) as live,sqlite3.connect(dbpath) as saved:
        live.backup(saved)
        saved.execute('PRAGMA journal_mode=DELETE')
    workspace_export(target/'workspace.tar.gz')
    files={p.relative_to(target).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in target.rglob('*') if p.is_file()}
    manifest={'format':1,'created':datetime.now(timezone.utc).isoformat(),'vm_id':vm_id,'model':settings.model,'platform':'iOS','contains_secrets':True,'files':files,
              'exclusions':['Full VM disk and running state','Installed Linux system/packages','Firefox profile and logins','Tailscale device identity','Ollama model weights','Workspace symlinks and special files','Windows scheduled-task installation']}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    result=verify(target,require_complete=False)
    (target/'COMPLETE').write_text(digest(target/'manifest.json')+'\n',encoding='ascii')
    print(json.dumps({'backup':str(target),**result},indent=2))
    return target


def verify(path,require_complete=True):
    path=Path(path).resolve()
    manifest_path=path/'manifest.json'
    if path.is_symlink() or manifest_path.is_symlink():raise ValueError('Backup links are not supported')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format')!=1:raise ValueError('Unsupported backup format')
    try:uuid.UUID(manifest['vm_id'])
    except (ValueError,TypeError,KeyError,AttributeError):raise ValueError('Invalid backup VM identity')
    if require_complete and (path/'COMPLETE').read_text(encoding='ascii').strip()!=digest(manifest_path):raise ValueError('Backup is incomplete or manifest changed')
    expected=set(manifest['files'])
    actual={p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}-{'manifest.json','COMPLETE'}
    if expected!=actual:raise ValueError('Missing or unexpected backup files')
    for name,info in manifest['files'].items():
        member=path.joinpath(*safe_member(name).parts)
        if member.is_symlink() or not member.resolve().is_relative_to(path):raise ValueError('Backup member escapes its directory')
        if member.stat().st_size!=info['bytes'] or digest(member)!=info['sha256']:raise ValueError('Backup file checksum mismatch')
    workspace=verify_workspace(path/'workspace.tar.gz')
    with sqlite3.connect((path/'private/tasks.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Task database integrity check failed')
        task_count=db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    return {'verified':True,'files':len(expected),'tasks':task_count,'workspace':workspace}


def restore(path,destination):
    path=Path(path).resolve();result=verify(path)
    destination=Path(destination).absolute()
    if destination.exists():raise ValueError('Restore destination must not exist')
    # Refuse any destination overlapping live source/private state or the backup.
    resolved=destination.resolve()
    if resolved==ROOT or ROOT.is_relative_to(resolved) or resolved.is_relative_to(path):raise ValueError('Unsafe restore destination')
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT/'.local/restore-checks'):
        raise ValueError('Inside the project, restore only under .local/restore-checks')
    # Validate host filenames before creating any staged workspace files.
    with tarfile.open(path/'workspace.tar.gz','r:gz') as archive:
        for member in archive:
            if member.name.startswith('workspace/'):
                safe_windows_member(member.name)
    private_directory(destination)
    for source in path.rglob('*'):
        if source.is_file():copy_file(source,destination/source.relative_to(path))
    # Restore workspace contents for inspection without extracting links or executing code.
    extracted=destination/'restored-workspace';extracted.mkdir()
    with tarfile.open(destination/'workspace.tar.gz','r:gz') as archive:
        for member in archive:
            name=safe_member(member.name)
            if not name.parts or name.parts[0]!='workspace':continue
            if not (member.isfile() or member.isdir()):raise ValueError('Unsafe workspace member')
            target=extracted.joinpath(*name.parts[1:])
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as output:shutil.copyfileobj(archive.extractfile(member),output)
    with tarfile.open(destination/'workspace.tar.gz','r:gz') as archive:
        workspace_manifest=json.load(archive.extractfile('workspace-manifest.json'))
    for name,info in workspace_manifest['files'].items():
        target=extracted.joinpath(*safe_member(name).parts)
        if target.stat().st_size!=info['bytes'] or digest(target)!=info['sha256']:raise ValueError('Restored workspace mismatch')
    # verify() intentionally rejects the additional extracted directory, so verify
    # the copied backup components individually against the original manifest.
    manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
    if any(digest(destination.joinpath(*safe_member(n).parts))!=v['sha256'] for n,v in manifest['files'].items()):raise ValueError('Restored component mismatch')
    with sqlite3.connect((destination/'private/tasks.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Restored database failed integrity check')
    proof={'restored':True,'staging_directory':str(destination),'verified_backup_files':result['files'],'tasks':result['tasks'],'workspace_files':result['workspace']['files'],'live_setup_modified':False}
    (destination/'RESTORE-VERIFIED.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof,indent=2));return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('create')
    check=sub.add_parser('verify');check.add_argument('path',type=Path)
    staged=sub.add_parser('restore');staged.add_argument('path',type=Path);staged.add_argument('destination',type=Path)
    args=parser.parse_args()
    if args.action=='create':create()
    elif args.action=='verify':print(json.dumps(verify(args.path),indent=2))
    else:restore(args.path,args.destination)

if __name__=='__main__':main()
