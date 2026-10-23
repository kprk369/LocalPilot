import asyncio
import pytest
from backend.linux_status import LinuxStatus
from backend.tools import validate

@pytest.mark.parametrize('desktop,workspace,state',[(True,True,'ready'),(False,True,'desktop_disconnected'),(True,False,'attention')])
def test_readiness_requires_real_guest_and_desktop(desktop,workspace,state):
    class Executor:
        calls=0
        async def execute(self,name,args):
            assert name=='system_status' and args=={}
            self.calls+=1
            return {'ok':True,'connected':True,'desktop_ready':desktop,'workspace_ready':workspace,'browser_installed':True}
    async def scenario():
        executor=Executor();probe=LinuxStatus(executor)
        results=await asyncio.gather(*[probe.get() for _ in range(5)])
        assert all(r['state']==state for r in results)
        assert executor.calls==1
    asyncio.run(scenario())

def test_failed_probe_does_not_keep_stale_ready_state():
    class Executor:
        fail=False
        async def execute(self,*args):
            if self.fail:raise OSError('SSH unavailable')
            return {'ok':True,'connected':True,'desktop_ready':True,'workspace_ready':True}
    async def scenario():
        executor=Executor();probe=LinuxStatus(executor,ttl=0)
        assert (await probe.get())['state']=='ready'
        executor.fail=True
        result=await probe.get()
        assert result['state']=='offline' and not result['connected'] and not result['desktop_ready']
    asyncio.run(scenario())

@pytest.mark.parametrize('url',['javascript:alert(1)','file:///etc/passwd','data:text/html,hello','https://user:pass@example.com/','https://example.com/ bad','https://example.com:99999/'])
def test_browser_rejects_non_web_urls_and_embedded_credentials(url):
    with pytest.raises(ValueError):validate('desktop_browser_open',{'observation_id':'11111111-1111-4111-8111-111111111111','url':url})

def test_browser_website_payload_uses_existing_approval_boundary():
    from backend.tools import DESKTOP_INPUTS
    assert 'desktop_browser_open' in DESKTOP_INPUTS
    assert validate('desktop_browser_open',{'observation_id':'11111111-1111-4111-8111-111111111111','url':'https://example.com/'})['url']=='https://example.com/'


def test_obsolete_screens_are_compacted_without_losing_request_or_latest_screen():
    import json
    from backend.agent import compact_desktop_context
    original={'role':'user','content':'Fill only the requested local form'}
    latest={'role':'tool','tool_name':'desktop_observe','content':json.dumps({'ok':True,'observation_id':'current','windows':[{'title':'Current page'}]})}
    image={'role':'user','content':'UNTRUSTED TOOL OBSERVATION current','images':['current-image']}
    messages=[{'role':'system','content':'policy'},original,{'role':'tool','tool_name':'read_file','content':'keep file evidence'}, {'role':'tool','tool_name':'desktop_observe','content':json.dumps({'ok':True,'observation_id':'old','windows':[{'title':'Old page'}]})},{'role':'user','content':'UNTRUSTED TOOL OBSERVATION old'},latest,image]
    result=compact_desktop_context(messages)
    assert original in result and latest in result and image in result
    assert any(m.get('content')=='keep file evidence' for m in result)
    assert not any(m.get('content')=='UNTRUSTED TOOL OBSERVATION old' for m in result)
    assert 'Old page' not in json.dumps(result)
    assert 'old' in messages[3]['content']  # Durable/source data is not rewritten.
