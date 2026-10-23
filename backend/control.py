"""One desktop owner; short guest actions serialize with ownership changes."""
import asyncio

class DesktopControl:
    def __init__(self, executor):
        self.executor=executor
        self.owner='agent'
        self.revision=0
        self.confirmed=False
        self.ready=asyncio.Event();self.ready.set()
        self.lock=asyncio.Lock()
        self.interrupt=None

    def state(self):
        return {'owner':self.owner,'revision':self.revision,'confirmed':self.confirmed}

    def apply(self,result):
        if result.get('owner') in ('agent','human'):
            self.owner=result['owner'];self.revision=result['revision'];self.confirmed=True
        if self.owner=='agent':self.ready.set()
        else:self.ready.clear()

    async def initialize(self):
        try:self.apply(await self.executor.execute('desktop_state',{}))
        except Exception:
            self.owner='human';self.ready.clear()

    async def change(self,owner):
        async with self.lock:
            self.ready.clear()
            self.confirmed=False
            if owner=='human':
                self.owner='human'
                if self.interrupt:await self.interrupt()
            result=await self.executor.execute('desktop_control',{'owner':owner})
            if not result.get('ok') or result.get('owner')!=owner or type(result.get('revision'))is not int:
                self.owner='human'
                raise RuntimeError(result.get('error','Could not change desktop owner'))
            self.apply(result)
            return self.state()
