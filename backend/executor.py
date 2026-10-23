"""Restricted-key SSH transport. No administrator key or password is used."""
import asyncio
import base64
from .config import ROOT
from .network import resolve_host
import json
import uuid

class LinuxExecutor:
    def __init__(self, settings):
        self.settings = settings

    async def _request(self, request, timeout=75):
        s = self.settings
        alias = ['-o', 'HostKeyAlias='+s.host_key_alias] if s.host_key_alias else []
        host = resolve_host(s.ssh_host, s.host_key_alias)
        process = await asyncio.create_subprocess_exec('ssh.exe', *alias, '-T', '-i', s.ssh_key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={s.known_hosts}', f'pilot@{host}', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(json.dumps(request).encode()), timeout)
            if process.returncode:
                raise RuntimeError('Linux SSH execution failed: ' + stderr.decode(errors='replace')[:400])
            result = json.loads(stdout)
            encoded = result.pop('image_jpeg', None)
            if encoded is not None:
                content = base64.b64decode(encoded, validate=True)
                if len(content) > 2*1024*1024 or not content.startswith(b'\xff\xd8'):
                    raise ValueError('Invalid desktop image')
                image_id = str(uuid.UUID(result['observation_id']))
                directory = ROOT / '.local/screenshots'
                directory.mkdir(exist_ok=True)
                (directory / (image_id+'.jpg')).write_bytes(content)
                result['image_url'] = '/screenshots/'+image_id
            return result
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    def image_for(self, observation_id):
        image_id = str(uuid.UUID(observation_id))
        return base64.b64encode((ROOT / '.local/screenshots' / (image_id+'.jpg')).read_bytes()).decode()

    async def package_request(self, operation, arguments):
        s=self.settings
        if not s.installer_key:raise ValueError('Package capability is not configured')
        alias=['-o','HostKeyAlias='+s.host_key_alias] if s.host_key_alias else []
        host=resolve_host(s.ssh_host,s.host_key_alias)
        process=await asyncio.create_subprocess_exec('ssh.exe',*alias,'-T','-i',s.installer_key,'-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+s.known_hosts,'lp-installer@'+host,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            out,err=await asyncio.wait_for(process.communicate(json.dumps({'operation':operation,**arguments}).encode()),75)
            if process.returncode:raise RuntimeError('Package channel failed: '+err.decode(errors='replace')[:300])
            return json.loads(out)
        finally:
            if process.returncode is None:process.kill();await process.wait()

    async def execute(self, tool, arguments):
        if tool=='system_status':return await self._request({'tool':tool,'arguments':arguments},timeout=6)
        if tool.startswith('package_'):
            operation={'package_plan':'plan','package_review':'review','package_status':'status','package_install':'start'}.get(tool)
            if not operation:raise ValueError('Unknown package operation')
            result=await self.package_request(operation,arguments)
            if tool!='package_install' or not result.get('ok'):return result
            # The root-managed job survives cancellation; never kill apt/dpkg here.
            for _ in range(120):
                await asyncio.sleep(3)
                result=await self.package_request('status',{'plan_id':arguments['plan_id']})
                if result.get('status') not in ('queued','installing'):
                    result['ok']=result.get('status')=='completed'
                    return result
            return {'ok':False,'status':'installing','plan_id':arguments['plan_id'],'error':'Installation continues in the background. Use package_status to check it.'}
        job = str(uuid.uuid4())
        try:
            return await self._request({'tool': tool, 'arguments': arguments, 'job_id': job})
        except (asyncio.CancelledError, TimeoutError):
            try:
                await asyncio.shield(self._request({'tool': 'cancel', 'arguments': {'job_id': job}}, timeout=15))
            finally:
                raise
