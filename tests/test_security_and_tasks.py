import asyncio
from dataclasses import replace
from fastapi.testclient import TestClient
import pytest
from backend.agent import Engine
from backend.api import create_app
from backend.config import Settings
from backend.store import Store
from backend.tools import validate

class FakeProvider:
    def __init__(self):
        self.calls = 0
    async def models(self):
        return []
    async def generate(self, messages, tools, on_token):
        self.calls += 1
        if self.calls == 1:
            return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'terminal_execute', 'arguments': {'command': 'printf approved'}}}]}, {}
        return {'role': 'assistant', 'content': 'Done'}, {}

class FakeExecutor:
    def __init__(self):
        self.calls = []
    async def execute(self, name, args):
        self.calls.append((name, args))
        return {'ok': True, 'exit_code': 0, 'output': 'approved'}

async def wait_for(predicate):
    for _ in range(1000):
        if predicate():
            return
        await asyncio.sleep(.001)
    raise AssertionError('State transition timed out')

@pytest.mark.parametrize('allow', [True, False])
def test_execution_requires_one_use_approval(tmp_path, allow):
    async def scenario():
        store = Store(str(tmp_path/'tasks.db'))
        executor = FakeExecutor()
        engine = Engine(store, FakeProvider(), executor)
        task_id = engine.submit('Run a command')
        await wait_for(lambda: task_id in engine.pending)
        assert executor.calls == []
        approval_id = engine.pending[task_id]['id']
        # Even in-memory mutation cannot alter the already reviewed command.
        engine.pending[task_id]['arguments']['command'] = 'unexpected command'
        engine.decide(task_id, approval_id, allow)
        with pytest.raises(ValueError):
            engine.decide(task_id, approval_id, True)
        await wait_for(lambda: task_id not in engine.running)
        assert len(executor.calls) == int(allow)
        if allow:
            assert executor.calls[0][1]['command'] == 'printf approved'
            assert store.get(task_id)['status'] == 'completed'
        else:
            assert store.get(task_id)['status'] == 'rejected'
        store.db.close()
    asyncio.run(scenario())

def test_cancel_pending_task_never_executes(tmp_path):
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'))
        executor=FakeExecutor()
        engine=Engine(store,FakeProvider(),executor)
        task_id=engine.submit('Run a command')
        await wait_for(lambda: task_id in engine.pending)
        await engine.cancel(task_id)
        assert executor.calls == []
        assert store.get(task_id)['status']=='cancelled'
        assert task_id not in engine.pending
        store.db.close()
    asyncio.run(scenario())

def test_restart_does_not_replay_work(tmp_path):
    path=str(tmp_path/'tasks.db')
    first=Store(path)
    first.create('old-task','Request')
    first.update('old-task','awaiting_approval')
    first.db.close()
    second=Store(path)
    assert second.get('old-task')['status']=='interrupted'
    second.db.close()

def test_tool_inputs_reject_unknown_fields_and_tools():
    with pytest.raises(ValueError):
        validate('terminal_execute',{'command':'id','approved':True})
    with pytest.raises(ValueError):
        validate('approve',{})
    with pytest.raises(ValueError):
        validate('terminal_execute',{'command':'id','timeout':True})
    with pytest.raises(ValueError):
        validate('terminal_execute',{'command':'id','timeout':61})

def test_api_requires_operator_token(tmp_path):
    settings=Settings(token='x'*40,ssh_host='127.0.0.1',ssh_key='unused',known_hosts='unused',database=str(tmp_path/'tasks.db'))
    with TestClient(create_app(settings,FakeProvider(),FakeExecutor())) as client:
        assert client.get('/health').status_code==401
        assert client.post('/tasks',json={'request':'hello'}).status_code==401
        assert client.get('/models',headers={'Authorization':'Bearer wrong'}).status_code==401
        assert client.get('/health',headers={'Authorization':'Bearer '+settings.token}).status_code==200
        assert client.post('/tasks',headers={'Authorization':'Bearer '+settings.token},json={'request':'x','approved':True}).status_code==422
