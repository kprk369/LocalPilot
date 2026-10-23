import asyncio
import os
import pytest
from backend.config import Settings
from backend.executor import LinuxExecutor
pytestmark=pytest.mark.skipif(os.getenv('LOCALPILOT_PACKAGE_INTEGRATION')!='1',reason='Live package channel tests are opt-in; preview only')

def test_live_preview_invalid_payload_and_fingerprint_do_not_install():
    async def scenario():
        executor=LinuxExecutor(Settings.load())
        plan=await executor.execute('package_plan',{'packages':['tree']})
        assert plan['ok'] and plan['status']=='planned'
        assert plan['plan']['requested']==['tree']
        denied=await executor.package_request('start',{'plan_id':plan['plan']['id'],'sha256':'0'*64})
        assert not denied['ok']
        status=await executor.execute('package_status',{'plan_id':plan['plan']['id']})
        assert status['status']=='planned'
        for request in ({'packages':['sudo']},{'packages':['tree'],'command':'id'}):
            denied=await executor.package_request('plan',request)
            assert not denied['ok']
        pilot=await executor.execute('terminal_execute',{'command':'sudo -n /usr/bin/python3 /usr/local/lib/localpilot/package_broker.py </dev/null','timeout':5})
        assert not pilot['ok']
    asyncio.run(scenario())
