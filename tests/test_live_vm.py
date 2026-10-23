"""Opt-in live tests run only against the configured LocalPilot pilot account."""
import asyncio
import os
import time
import uuid
import pytest
from backend.config import Settings
from backend.executor import LinuxExecutor

pytestmark=pytest.mark.skipif(os.getenv('LOCALPILOT_INTEGRATION')!='1',reason='Live VM tests are opt-in')


def test_live_workspace_boundaries_and_account():
    async def scenario():
        executor=LinuxExecutor(Settings.load())
        for path in ['../escape.txt','/etc/shadow']:
            result=await executor.execute('read_file',{'path':path})
            assert not result['ok']
        result=await executor.execute('terminal_execute',{'command':'id -un; sudo -n true','timeout':5})
        assert not result['ok']
        assert result['output'].startswith('pilot\n')
        assert 'sudo' in result['output']
        link=f'integration-tests/symlink-{uuid.uuid4()}'
        await executor.execute('terminal_execute',{'command':f'mkdir -p integration-tests; ln -s /etc {link}','timeout':5})
        escaped=await executor.execute('read_file',{'path':link+'/passwd'})
        assert not escaped['ok']
        private=await executor.execute('terminal_execute',{'command':'cat /opt/localpilot/config/bootstrap.json','timeout':5})
        assert not private['ok'] and 'Permission denied' in private['output']
        path=f'integration-tests/{uuid.uuid4()}/unicode.txt'
        write=await executor.execute('write_file',{'path':path,'content':'LocalPilot ✓\n'})
        read=await executor.execute('read_file',{'path':path})
        assert write['ok'] and read['ok']
        assert read['content']=='LocalPilot ✓\n'
        assert write['sha256']==read['sha256']
    asyncio.run(scenario())


def test_live_terminal_timeout_and_output_limit():
    async def scenario():
        executor=LinuxExecutor(Settings.load())
        result=await executor.execute('terminal_execute',{'command':'sleep 10','timeout':1})
        assert result['timed_out'] and not result['ok']
        result=await executor.execute('terminal_execute',{'command':'python3 -c "print(\'x\'*100000)"','timeout':5})
        assert result['truncated'] and len(result['output'])==65536
    asyncio.run(scenario())


def test_live_cancel_kills_remote_process():
    async def scenario():
        executor=LinuxExecutor(Settings.load())
        marker=f'cancel-test-{uuid.uuid4()}.txt'
        task=asyncio.create_task(executor.execute('terminal_execute',{'command':f'sleep 5; touch {marker}','timeout':15}))
        await asyncio.sleep(1.5)
        start=time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic()-start<5
        await asyncio.sleep(5)
        result=await executor.execute('read_file',{'path':marker})
        assert not result['ok']
    asyncio.run(scenario())


def test_cancel_before_remote_start_blocks_execution():
    async def scenario():
        executor=LinuxExecutor(Settings.load())
        job=str(uuid.uuid4())
        await executor._request({'tool':'cancel','arguments':{'job_id':job}})
        result=await executor._request({'tool':'terminal_execute','arguments':{'command':'echo should-not-run'},'job_id':job})
        assert result['cancelled'] and not result['ok']
    asyncio.run(scenario())
