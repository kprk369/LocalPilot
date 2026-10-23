import asyncio
import os
import uuid
import pytest
from backend.config import Settings
from backend.executor import LinuxExecutor
pytestmark=pytest.mark.skipif(os.getenv('LOCALPILOT_INTEGRATION')!='1',reason='Live guest routines are opt-in')


def test_live_guest_routine_grammar_and_workspace_enforcement():
    async def scenario():
        executor=LinuxExecutor(Settings.load());folder='integration-tests/routine-'+uuid.uuid4().hex[:12]
        result=await executor.execute('terminal_routine',{'command':'mkdir -p '+folder})
        assert result['ok']
        assert (await executor.execute('write_file',{'path':folder+'/text','content':'routine check\n'}))['ok']
        read=await executor.execute('terminal_routine',{'command':'cat '+folder+'/text'})
        assert read['ok'] and read['output']=='routine check\n' and read['execution_mode']=='routine-v1'
        # Create an escaping link only in this unique test directory.
        link=await executor.execute('terminal_execute',{'command':'ln -s /etc '+folder+'/outside','timeout':5})
        assert link['ok']
        for command in ['cat '+folder+'/outside/passwd','ls '+folder+'/outside','cat /etc/passwd','cat ../secret','python3 script.py','ls; id','echo hi > '+folder+'/bad']:
            denied=await executor.execute('terminal_routine',{'command':command})
            assert not denied['ok'],command
        missing=await executor.execute('read_file',{'path':folder+'/bad'})
        assert not missing['ok']
        protection=await executor.execute('terminal_execute',{'command':'stat -c "%U %a" /usr/local/lib/localpilot/routine_commands.py; test ! -w /usr/local/lib/localpilot/routine_commands.py','timeout':5})
        assert protection['ok'] and protection['output'].strip()=='root 644'
    asyncio.run(scenario())
