import asyncio
import importlib.util
import time
from pathlib import Path
import pytest
from backend.agent import Engine
from backend.store import Store
from backend.tools import validate
from test_security_and_tasks import FakeProvider, wait_for
spec=importlib.util.spec_from_file_location('package_broker',Path(__file__).resolve().parents[1]/'vm/provisioning/package_broker.py')
broker=importlib.util.module_from_spec(spec);spec.loader.exec_module(broker)

def test_package_plan_refuses_removal_upgrade_and_unrelated_configuration():
    assert broker.parse_actions('Inst tree (2.1.1-2 Ubuntu:24.04/noble [amd64])\nConf tree (2.1.1-2 Ubuntu:24.04/noble [amd64])')==[{'package':'tree','version':'2.1.1-2'}]
    for output in ('Remv tree [1.0]','Inst tree [1.0] (2.0 Ubuntu [amd64])','Conf openssh-server (1 Ubuntu [amd64])'):
        with pytest.raises(ValueError):broker.parse_actions(output)

def test_package_catalog_and_payload_are_strict():
    for args in ({'packages':['sudo']},{'packages':['tree'],'command':'id'},{'packages':['tree; id']}):
        with pytest.raises(ValueError):validate('package_plan',args)
    for request in ({'operation':'shell','command':'id'},{'operation':'plan','packages':['sudo']},{'operation':'plan','packages':['tree','tree']},{'operation':'plan','packages':['tree'],'approved':True}):
        with pytest.raises(ValueError):broker.dispatch(request)

def test_package_plan_hash_expiry_and_single_use():
    plan={'expires':time.time()+60,'actions':[]}
    record={'plan':plan,'sha256':broker.digest(plan),'status':'planned'}
    assert broker.verify_plan(record,record['sha256'])==plan
    with pytest.raises(ValueError):broker.verify_plan(record,'0'*64)
    record['status']='queued'
    with pytest.raises(ValueError):broker.verify_plan(record,record['sha256'])
    record['status']='planned';plan['expires']=0;record['sha256']=broker.digest(plan)
    with pytest.raises(ValueError):broker.verify_plan(record,record['sha256'])

@pytest.mark.parametrize('allow',[True,False])
def test_installation_requires_exact_operator_approval(tmp_path,allow):
    class Provider(FakeProvider):
        async def generate(self,messages,tools,on_token):
            self.calls+=1
            if self.calls==1:return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'package_install','arguments':{'plan_id':'11111111-1111-4111-8111-111111111111','sha256':'a'*64}}}]},{}
            return {'role':'assistant','content':'Installation verified'},{}
    class Executor:
        def __init__(self):self.calls=[]
        async def execute(self,name,args):
            self.calls.append((name,args))
            if name=='package_review':return {'ok':True,'status':'planned','sha256':'a'*64,'plan':{'requested':['tree'],'actions':[{'package':'tree','version':'2.1'}]}}
            return {'ok':True,'status':'completed'}
    async def scenario():
        store=Store(str(tmp_path/'tasks.db'));executor=Executor();engine=Engine(store,Provider(),executor)
        tid=engine.submit('Install tree')
        await wait_for(lambda:tid in engine.pending)
        assert [x[0] for x in executor.calls]==['package_review']
        assert engine.pending[tid]['review']['requested']==['tree']
        engine.pending[tid]['arguments']['sha256']='b'*64
        engine.decide(tid,engine.pending[tid]['id'],allow)
        await wait_for(lambda:tid not in engine.running)
        installs=[args for name,args in executor.calls if name=='package_install']
        assert len(installs)==int(allow)
        if allow:assert installs[0]['sha256']=='a'*64
        store.db.close()
    asyncio.run(scenario())
