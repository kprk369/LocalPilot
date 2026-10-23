import asyncio
import pytest
from backend.agent import Engine
from backend.control import DesktopControl
from backend.store import Store
from backend.tools import validate
from test_security_and_tasks import FakeProvider, wait_for

class DesktopExecutor:
    def __init__(self):
        self.owner='agent';self.revision=0;self.calls=[];self.started=asyncio.Event();self.stopped=False
    async def execute(self,name,args):
        if name=='desktop_state':return {'ok':True,'owner':self.owner,'revision':self.revision}
        if name=='desktop_control':
            if self.owner!=args['owner']:self.revision+=1
            self.owner=args['owner'];return {'ok':True,'owner':self.owner,'revision':self.revision}
        self.calls.append((name,args))
        if name=='terminal_execute':
            self.started.set()
            try:await asyncio.sleep(60)
            finally:self.stopped=True
        return {'ok':True}

class RecoveryProvider(FakeProvider):
    async def generate(self,messages,tools,on_token):
        self.calls+=1
        if self.calls==1:return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'terminal_execute','arguments':{'command':'sleep 60'}}}]},{}
        if self.calls==2:return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'list_files','arguments':{}}}]},{}
        return {'role':'assistant','content':'Inspected after resuming'},{}

def test_takeover_interrupts_operation_and_pauses_until_resume(tmp_path):
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));executor=DesktopExecutor();control=DesktopControl(executor);await control.initialize();provider=RecoveryProvider();engine=Engine(store,provider,executor,control);control.interrupt=engine.interrupt_tools
        tid=engine.submit('Inspect after interruption')
        await wait_for(lambda:tid in engine.pending)
        engine.decide(tid,engine.pending[tid]['id'],True)
        await executor.started.wait()
        result=await control.change('human')
        await wait_for(lambda:store.get(tid)['status']=='paused')
        assert result['owner']=='human' and result['confirmed']
        assert executor.stopped and provider.calls==1
        await asyncio.sleep(.02)
        assert provider.calls==1
        await control.change('agent')
        await wait_for(lambda:tid not in engine.running)
        assert store.get(tid)['status']=='completed'
        assert executor.calls[-1][0]=='list_files'
        store.db.close()
    asyncio.run(scenario())

def test_takeover_invalidates_previously_reviewed_command(tmp_path):
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));executor=DesktopExecutor();control=DesktopControl(executor);await control.initialize();engine=Engine(store,FakeProvider(),executor,control)
        tid=engine.submit('Run a command');await wait_for(lambda:tid in engine.pending)
        approval=engine.pending[tid]['id'];await control.change('human')
        with pytest.raises(ValueError):engine.decide(tid,approval,True)
        await control.change('agent');engine.decide(tid,approval,True)
        await wait_for(lambda:tid not in engine.running)
        assert not executor.calls
        assert store.get(tid)['status']=='failed'
        store.db.close()
    asyncio.run(scenario())

def test_reject_is_allowed_while_human_controls_desktop(tmp_path):
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));executor=DesktopExecutor();control=DesktopControl(executor);await control.initialize();engine=Engine(store,FakeProvider(),executor,control)
        tid=engine.submit('Run a command');await wait_for(lambda:tid in engine.pending)
        approval=engine.pending[tid]['id'];await control.change('human');engine.decide(tid,approval,False)
        await wait_for(lambda:tid not in engine.running)
        assert store.get(tid)['status']=='rejected' and not executor.calls
        store.db.close()
    asyncio.run(scenario())

def test_desktop_schemas_reject_ownership_commands_and_bad_coordinates():
    for name,args in [('desktop_control',{'owner':'agent'}),('desktop_click',{'observation_id':'x','x':0,'y':0}),('desktop_keypress',{'observation_id':'00000000-0000-0000-0000-000000000000','key':'ctrl+alt+Delete'})]:
        with pytest.raises(ValueError):validate(name,args)


def test_observation_reaches_model_without_image_bytes_in_logs(tmp_path):
    class ImageExecutor:
        async def execute(self,name,args):return {'ok':True,'observation_id':'00000000-0000-0000-0000-000000000001','image_url':'/screenshots/example'}
        def image_for(self,observation_id):return 'private-base64-image'
    class ImageProvider:
        def __init__(self):self.calls=0;self.seen=False
        async def generate(self,messages,tools,on_token):
            self.calls+=1
            if self.calls==1:return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'desktop_observe','arguments':{}}}]},{}
            self.seen=messages[-1]['images']==['private-base64-image']
            return {'role':'assistant','content':'Desktop observed'},{}
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));provider=ImageProvider();engine=Engine(store,provider,ImageExecutor());tid=engine.submit('Observe')
        await wait_for(lambda:tid not in engine.running)
        assert provider.seen and 'private-base64-image' not in str(store.events(tid))
        store.db.close()
    asyncio.run(scenario())
