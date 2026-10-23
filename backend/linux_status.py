"""Short-lived, shared readiness checks; never infer VM readiness from HTTP health."""
import asyncio
import time

class LinuxStatus:
    def __init__(self,executor,ttl=5):
        self.executor=executor;self.ttl=ttl;self.lock=asyncio.Lock();self.cached=None;self.expires=0

    async def get(self):
        if self.cached is not None and time.monotonic()<self.expires:return self.cached
        async with self.lock:
            if self.cached is not None and time.monotonic()<self.expires:return self.cached
            try:
                result=await asyncio.wait_for(self.executor.execute('system_status',{}),timeout=8)
                connected=result.get('ok') is True and result.get('connected') is True
                desktop=connected and result.get('desktop_ready') is True
                workspace=connected and result.get('workspace_ready') is True
                browser=connected and result.get('browser_installed') is True
                state='offline' if not connected else 'attention' if not workspace else 'ready' if desktop else 'desktop_disconnected'
            except Exception:
                state='offline';connected=desktop=workspace=browser=False
            messages={'ready':'Linux is reachable and the shared desktop is ready.','desktop_disconnected':'Linux is connected. Open Desktop and connect to start the graphical session.','attention':'Linux is reachable, but its workspace needs attention.','offline':'Cannot reach Linux. Check that the VM is running and the private connection has recovered.'}
            self.cached={'state':state,'connected':connected,'desktop_ready':desktop,'workspace_ready':workspace,'browser_installed':browser,'checked_at':time.time(),'message':messages[state]}
            self.expires=time.monotonic()+self.ttl
            return self.cached
