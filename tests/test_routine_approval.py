import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.agent import Engine
from backend.api import create_app
from backend.auth import password_hash
from backend.config import Settings
from backend.store import Store
from backend.tools import validate
from vm.provisioning.routine_commands import eligible,execute
from test_security_and_tasks import FakeProvider,FakeExecutor,wait_for

@pytest.mark.parametrize('command',['pwd','whoami','python3 --version','echo "hello world"','ls','ls -la .','cat notes.txt','head -n 2 notes.txt','tail -n 200 notes.txt','wc -l notes.txt','mkdir -p "my folder/sub"'])
def test_fixed_routine_grammar_accepts_only_known_forms(command):assert eligible(command)

@pytest.mark.parametrize('command',['sudo id','rm file','python3 script.py','python3 -c "print(1)"','bash script','ls; id','ls && id','ls | cat','cat < file','echo hi > file','echo $(id)','echo `id`','cat /etc/passwd','cat ../secret','cat *','ls -R','cat --help','head -n 201 a','ls\nwhoami','NAME=x ls','/bin/ls','git status','curl https://example.com','mkdir -m 777 x','ls -l -a','cat C:/secret','echo ~','cat a\\b'])
def test_shell_scripts_external_paths_and_unknown_options_need_approval(command):assert not eligible(command)


def test_guest_routine_execution_is_bounded_and_confined(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'one two\nthree\n')
    assert execute('cat a.txt',tmp_path)['output']=='one two\nthree\n'
    assert execute('head -n 1 a.txt',tmp_path)['output']=='one two\n'
    assert execute('tail -n 1 a.txt',tmp_path)['output']=='three\n'
    assert execute('wc -l a.txt',tmp_path)['output']=='2 a.txt\n'
    execute('mkdir -p folder/sub',tmp_path)
    assert (tmp_path/'folder/sub').is_dir()
    assert execute('echo "hello world"',tmp_path)['output']=='hello world\n'
    (tmp_path/'large').write_bytes(b'x'*65537)
    with pytest.raises(ValueError,match='limit'):execute('cat large',tmp_path)
    with pytest.raises(ValueError):execute('cat ../escape',tmp_path)
    with pytest.raises(ValueError):validate('terminal_routine',{'command':'pwd'})


def test_setting_default_and_restart_persistence(tmp_path):
    path=str(tmp_path/'state.db');store=Store(path)
    assert not store.routine_approval()
    store.set_routine_approval(True);store.db.close()
    store=Store(path);assert store.routine_approval()
    store.set_routine_approval(False);store.db.close()
    store=Store(path);assert not store.routine_approval();store.db.close()


@pytest.mark.parametrize('enabled,command,automatic',[(False,'pwd',False),(True,'pwd',True),(True,'rm file',False),(True,'python3 script.py',False)])
def test_engine_only_skips_review_for_enabled_routine_grammar(tmp_path,enabled,command,automatic):
    class Provider(FakeProvider):
        async def generate(self,messages,tools,on_token):
            self.calls+=1
            if self.calls==1:return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'terminal_execute','arguments':{'command':command}}}]},{}
            return {'role':'assistant','content':'Done'},{}
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));store.set_routine_approval(enabled)
        executor=FakeExecutor();engine=Engine(store,Provider(),executor);task=engine.submit('test')
        await wait_for(lambda:task in engine.pending or task not in engine.running)
        if automatic:
            assert store.get(task)['status']=='completed'
            assert executor.calls==[('terminal_routine',{'command':command,'timeout':30})]
            events=store.events(task)
            assert any(e['kind']=='auto_approved' and e['data']['policy']=='routine-v1' for e in events)
            assert not any(e['kind']=='approval_requested' for e in events)
        else:
            assert executor.calls==[]
            engine.decide(task,engine.pending[task]['id'],False)
            await wait_for(lambda:task not in engine.running)
            assert store.get(task)['status']=='rejected'
        await engine.close();store.db.close()
    asyncio.run(scenario())


def test_enabling_does_not_consume_a_pending_approval(tmp_path):
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));executor=FakeExecutor()
        engine=Engine(store,FakeProvider(),executor);task=engine.submit('test')
        await wait_for(lambda:task in engine.pending)
        store.set_routine_approval(True)
        await asyncio.sleep(.01)
        assert task in engine.pending and executor.calls==[]
        await engine.cancel(task);store.db.close()
    asyncio.run(scenario())


def test_automation_api_requires_authentication_origin_and_strict_boolean(tmp_path):
    settings=Settings(token='x'*40,ssh_host='127.0.0.1',ssh_key='unused',known_hosts='unused',database=str(tmp_path/'tasks.db'),password_hash=password_hash('secret'),public_origin='https://testserver')
    with TestClient(create_app(settings,FakeProvider(),FakeExecutor()),base_url='https://testserver') as client:
        assert client.get('/settings/automation').status_code==401
        assert client.post('/settings/automation',json={'routine_commands':True}).status_code==401
        assert client.post('/session',json={'username':'localpilot','password':'secret'},headers={'Origin':'https://testserver'}).status_code==200
        assert client.get('/settings/automation').json()['routine_commands'] is False
        assert client.post('/settings/automation',json={'routine_commands':True}).status_code==403
        assert client.post('/settings/automation',json={'routine_commands':True},headers={'Origin':'https://evil.example'}).status_code==403
        headers={'Origin':'https://testserver'}
        for payload in [{'routine_commands':'true'},{'routine_commands':1},{'routine_commands':True,'all_commands':True}]:
            assert client.post('/settings/automation',json=payload,headers=headers).status_code==422
        assert client.post('/settings/automation',json={'routine_commands':True},headers=headers).json()['routine_commands'] is True
        assert client.get('/settings/automation').json()['routine_commands'] is True
        assert client.post('/settings/automation',json={'routine_commands':False},headers=headers).json()['routine_commands'] is False


@pytest.mark.parametrize('tool,args',[('desktop_keypress',{'observation_id':'11111111-1111-4111-8111-111111111111','key':'Return'}),('package_install',{'plan_id':'11111111-1111-4111-8111-111111111111','sha256':'a'*64})])
def test_enabling_routines_never_bypasses_gui_or_package_review(tmp_path,tool,args):
    class Provider(FakeProvider):
        async def generate(self,messages,tools,on_token):
            return {'role':'assistant','content':'','tool_calls':[{'function':{'name':tool,'arguments':args}}]},{}
    class Executor(FakeExecutor):
        async def execute(self,name,arguments):
            self.calls.append((name,arguments))
            if name=='package_review':return {'ok':True,'sha256':'a'*64,'status':'planned','plan':{'requested':['tree'],'actions':[]}}
            raise AssertionError('An input executed before review')
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));store.set_routine_approval(True)
        executor=Executor();engine=Engine(store,Provider(),executor);task=engine.submit('test')
        await wait_for(lambda:task in engine.pending)
        assert engine.pending[task]['tool']==tool
        assert all(name=='package_review' for name,_ in executor.calls)
        engine.decide(task,engine.pending[task]['id'],False)
        await wait_for(lambda:task not in engine.running)
        assert store.get(task)['status']=='rejected'
        store.db.close()
    asyncio.run(scenario())
