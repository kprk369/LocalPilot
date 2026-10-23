"""Explicitly opt-in harmless GUI actions on the existing LocalPilot desktop."""
import asyncio,json,os,uuid
from pathlib import Path
import pytest
from backend.config import Settings
from backend.executor import LinuxExecutor
pytestmark=pytest.mark.skipif(os.getenv('LOCALPILOT_GUI_INTEGRATION')!='1',reason='Live desktop tests are opt-in')

def test_live_gui_input_and_fresh_observations():
    async def scenario():
        e=LinuxExecutor(Settings.load())
        await e.execute('desktop_control',{'owner':'agent'})
        async def observe():
            result=await e.execute('desktop_observe',{})
            assert result['ok'],result
            assert result['display'].startswith(':10')
            return result
        shot=await observe()
        out=await e.execute('desktop_click',{'observation_id':shot['observation_id'],'x':shot['image_width'],'y':0})
        assert not out['ok']
        existing={w['id']for w in shot['windows']if w['title']=='LocalPilot'}
        opened=await e.execute('desktop_open_application',{'observation_id':shot['observation_id'],'application':'terminal'})
        assert opened['ok'],opened
        repeated=await e.execute('desktop_keypress',{'observation_id':shot['observation_id'],'key':'Escape'})
        assert not repeated['ok']
        await asyncio.sleep(.5)
        shot=await observe();window=next(w for w in shot['windows'] if w['title']=='LocalPilot'and w['id']not in existing)
        focused=await e.execute('desktop_focus_window',{'observation_id':shot['observation_id'],'window_id':window['id']})
        assert focused['ok']and focused['active_window_id']==window['id'],focused
        shot=await observe();window=next(w for w in shot['windows']if w['id']==window['id'])
        x=min(shot['width']-1,max(0,window['x']+30));y=min(shot['height']-1,max(0,window['y']+60))
        result=await e.execute('desktop_click',{'observation_id':shot['observation_id'],'x':round(x*shot['image_width']/shot['width']),'y':round(y*shot['image_height']/shot['height'])})
        assert result['ok'] and result['active_window']=='LocalPilot',result
        shot=await observe()
        result=await e.execute('desktop_scroll',{'observation_id':shot['observation_id'],'direction':'up','amount':1})
        assert result['ok'],result
        shot=await observe()
        focused=await e.execute('desktop_focus_window',{'observation_id':shot['observation_id'],'window_id':window['id']})
        assert focused['ok'],focused
        shot=await observe()
        marker='gui-input-'+str(uuid.uuid4())+'.txt'
        typed=await e.execute('desktop_type',{'observation_id':shot['observation_id'],'text':'printf LocalPilot-GUI-input-passed > /home/pilot/Workspace/'+marker})
        assert typed['ok'],typed
        shot=await observe()
        pressed=await e.execute('desktop_keypress',{'observation_id':shot['observation_id'],'key':'Return'})
        assert pressed['ok'],pressed
        await asyncio.sleep(.25)
        result=await e.execute('read_file',{'path':marker})
        assert result['ok'] and result['content']=='LocalPilot-GUI-input-passed',result
        proof=await observe();Path('.local/gui-input-proof.json').write_text(json.dumps(proof,indent=2))
        closed=await e.execute('desktop_keypress',{'observation_id':proof['observation_id'],'key':'alt+F4'})
        assert closed['ok']
    asyncio.run(scenario())

def test_live_human_control_blocks_input_and_invalidates_observations():
    async def scenario():
        e=LinuxExecutor(Settings.load());await e.execute('desktop_control',{'owner':'agent'})
        before=await e.execute('desktop_observe',{})
        try:
            human=await e.execute('desktop_control',{'owner':'human'})
            assert human['ok'] and human['owner']=='human'
            shot=await e.execute('desktop_observe',{});assert shot['ok']
            result=await e.execute('desktop_type',{'observation_id':shot['observation_id'],'text':'MUST_NOT_TYPE'})
            assert not result['ok'] and 'Human controls' in result['error']
        finally:await e.execute('desktop_control',{'owner':'agent'})
        result=await e.execute('desktop_keypress',{'observation_id':before['observation_id'],'key':'Return'})
        assert not result['ok']
    asyncio.run(scenario())
