"""Forced-command SSH executor. Installed root-owned; runs as unprivileged pilot."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import uuid

WORKSPACE = Path.home() / 'Workspace'
JOBS = Path.home() / '.local/state/localpilot/jobs'
MAX_BYTES = 65536


def workspace_path(value):
    if not isinstance(value, str) or len(value) > 512 or '\x00' in value:
        raise ValueError('Invalid workspace path')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Path must be relative to the workspace')
    target = (WORKSPACE / relative).resolve()
    target.relative_to(WORKSPACE.resolve())
    return target


def arguments(data, allowed, required):
    if not isinstance(data, dict) or set(data) - set(allowed) or set(required) - set(data):
        raise ValueError('Unexpected or missing tool arguments')


def process_start(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (65, 65))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16*1024**2, 16*1024**2))
    # Linux counts all threads owned by pilot, including its shared Firefox desktop.
    resource.setrlimit(resource.RLIMIT_NPROC, (2048, 2048))


def dispatch(request):
    tool = request['tool']
    data = request.get('arguments', {})
    if tool=='terminal_routine':
        arguments(data,['command','timeout'],['command'])
        from routine_commands import execute
        return execute(data['command'],WORKSPACE)
    if tool=='system_status':
        arguments(data,[],[])
        ready=False
        try:
            from desktop_tools import desktop
            desktop();ready=True
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):pass
        return {'ok':True,'connected':True,'desktop_ready':ready,'workspace_ready':WORKSPACE.is_dir() and os.access(WORKSPACE,os.R_OK|os.W_OK|os.X_OK),'browser_installed':Path('/usr/bin/firefox').is_file()}
    if isinstance(tool,str) and tool.startswith('desktop_'):
        from desktop_tools import dispatch as desktop_dispatch
        return desktop_dispatch(tool,data)
    if tool == 'cancel':
        arguments(data, ['job_id'], ['job_id'])
        job = str(uuid.UUID(data['job_id']))
        JOBS.mkdir(parents=True, exist_ok=True, mode=0o700)
        (JOBS / f'{job}.cancel').touch()
        jobfile = JOBS / f'{job}.json'
        if not jobfile.exists():
            return {'ok': True, 'cancelled': False}
        record = json.loads(jobfile.read_text())
        try:
            if process_start(record['pid']) == record['start']:
                os.killpg(record['pid'], signal.SIGKILL)
                return {'ok': True, 'cancelled': True}
        except ProcessLookupError:
            pass
        return {'ok': True, 'cancelled': False}
    if tool in ('list_files', 'read_file', 'make_directory'):
        arguments(data, ['path'], [] if tool == 'list_files' else ['path'])
        target = workspace_path(data.get('path', '.'))
        if tool == 'list_files':
            entries = sorted(target.iterdir(), key=lambda p: p.name)
            return {'ok': True, 'entries': [{'name': p.name, 'directory': p.is_dir()} for p in entries[:200]], 'truncated': len(entries) > 200}
        if tool == 'make_directory':
            target.mkdir(parents=True, exist_ok=True)
            return {'ok': True, 'path': data['path'], 'exists': target.is_dir()}
        with target.open('rb') as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('File exceeds read limit')
        return {'ok': True, 'path': data['path'], 'content': content.decode('utf-8'), 'sha256': hashlib.sha256(content).hexdigest()}
    if tool == 'write_file':
        arguments(data, ['path', 'content'], ['path', 'content'])
        target = workspace_path(data['path'])
        if not isinstance(data['content'], str):
            raise ValueError('Content must be text')
        content = data['content'].encode('utf-8')
        if len(content) > MAX_BYTES:
            raise ValueError('File exceeds write limit')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(content)
        try:
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return {'ok': True, 'path': data['path'], 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    if tool == 'terminal_execute':
        arguments(data, ['command', 'timeout'], ['command'])
        command = data['command']
        timeout = data.get('timeout', 30)
        if not isinstance(command, str) or not 1 <= len(command) <= 4096 or '\x00' in command:
            raise ValueError('Invalid shell command')
        if type(timeout) is not int or not 1 <= timeout <= 60:
            raise ValueError('Timeout must be 1 to 60 seconds')
        job = str(uuid.UUID(request['job_id']))
        JOBS.mkdir(parents=True, exist_ok=True, mode=0o700)
        jobfile = JOBS / f'{job}.json'
        if jobfile.exists():
            raise ValueError('Duplicate running job')
        if (JOBS / f'{job}.cancel').exists():
            return {'ok': False, 'cancelled': True, 'error': 'Job was cancelled before execution'}
        environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(Path.home()), 'USER': 'pilot', 'LANG': 'C.UTF-8'}
        with tempfile.TemporaryFile() as output:
            proc = subprocess.Popen(['/bin/bash', '-c', command], cwd=WORKSPACE, env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
            timed_out = False
            try:
                try:
                    start = process_start(proc.pid)
                except FileNotFoundError:
                    start = None
                if start:
                    jobfile.write_text(json.dumps({'pid': proc.pid, 'start': start}))
                if (JOBS / f'{job}.cancel').exists():
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            finally:
                # Reap background descendants as well as the shell itself.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                jobfile.unlink(missing_ok=True)
            output.seek(0)
            content = output.read(MAX_BYTES + 1)
        return {'ok': proc.returncode == 0 and not timed_out, 'exit_code': proc.returncode, 'output': content[:MAX_BYTES].decode('utf-8', errors='replace'), 'truncated': len(content) > MAX_BYTES, 'timed_out': timed_out}
    raise ValueError('Unknown tool')


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES * 2 + 1)
        if len(raw) > MAX_BYTES * 2:
            raise ValueError('Request exceeds input limit')
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) - {'tool', 'arguments', 'job_id'}:
            raise ValueError('Invalid request')
        WORKSPACE.mkdir(exist_ok=True)
        result = dispatch(request)
    except Exception as error:
        result = {'ok': False, 'error': f'{type(error).__name__}: {error}'}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
