"""Opt-in real-model reliability checks; never grants tool approvals.

Run from the project root: .venv\\Scripts\\python.exe -m scripts.reliability_check
Writes only unique QA workspace files and private local evidence. It refuses
an active queue or human ownership, and cancels only tasks it created.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid
import httpx
from backend.config import Settings, ROOT
from backend.executor import LinuxExecutor

ACTIVE={'queued','running','paused','awaiting_approval'}

async def main():
    settings=Settings.load()
    run_id=uuid.uuid4().hex[:12]
    folder='integration-tests/reliability-'+run_id
    executor=LinuxExecutor(settings)
    report={'run_id':run_id,'started':datetime.now(timezone.utc).isoformat(),
            'model':settings.model,'scope':'Ollama 27B; iOS only','cases':[]}
    output=ROOT/'.local/reliability'/('run-'+run_id+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',headers={'Authorization':'Bearer '+settings.token},trust_env=False,timeout=20) as client:
        async def get(path):
            r=await client.get(path);r.raise_for_status();return r.json()
        async def post(path,body=None):
            r=await client.post(path,json=body);r.raise_for_status();return r.json()
        if any(t['status'] in ACTIVE for t in await get('/tasks')):
            raise RuntimeError('Refusing to test while another task is active')
        control=await get('/desktop/state')
        if control.get('owner')!='agent' or not control.get('confirmed'):
            raise RuntimeError('Resume AI before running reliability checks')
        report['initial_readiness']=await get('/linux/status');save()
        async def run_case(name,request,policy='complete',expected=None,absent=None):
            # Do not queue behind work submitted independently during the checks.
            if any(t['status'] in ACTIVE for t in await get('/tasks')):
                raise RuntimeError('Another task became active; stopping checks')
            start=time.monotonic();task_id=(await post('/tasks',{'request':request}))['id']
            case={'name':name,'task_id':task_id,'policy':policy};report['cases'].append(case);save()
            decided=False
            try:
                while time.monotonic()-start<240:
                    row=await get('/tasks/'+task_id)
                    if row['status']=='awaiting_approval' and not decided:
                        approval=row['approval'];case['reviewed_tool']=approval['tool']
                        if policy=='reject':
                            await post('/tasks/'+task_id+'/approval',{'approval_id':approval['id'],'allow':False})
                        else:
                            await post('/tasks/'+task_id+'/cancel')
                        decided=True
                    if row['status'] not in ACTIVE:break
                    await asyncio.sleep(.5)
                else:
                    await post('/tasks/'+task_id+'/cancel')
                    row=await get('/tasks/'+task_id);case['deadline_exceeded']=True
                events=await get('/tasks/'+task_id+'/events')
                case.update(status=row['status'],elapsed_seconds=round(time.monotonic()-start,2),result=row.get('result'),events=events)
                tools=[e for e in events if e['kind']=='tool_result']
                case['tool_results']=len(tools)
                verified=True
                case['independent_files']=[]
                for path,content in (expected or {}).items():
                    actual=await executor.execute('read_file',{'path':path})
                    match=bool(actual.get('ok')) and actual.get('content')==content
                    case['independent_files'].append({'path':path,'matches':match,'sha256':actual.get('sha256')})
                    verified &= match
                if absent:
                    actual=await executor.execute('read_file',{'path':absent})
                    case['marker_absent']=not actual.get('ok')
                    verified &= case['marker_absent'] and not any(e['kind']=='tool_started' and e['data'].get('tool')=='terminal_execute' for e in events)
                wanted={'complete':'completed','reject':'rejected','cancel':'cancelled'}[policy]
                case['passed']=row['status']==wanted and verified and not case.get('deadline_exceeded',False)
                if policy!='complete':case['passed'] &= decided and case.get('reviewed_tool')=='terminal_execute'
                print(json.dumps({k:case[k] for k in ['name','status','passed','elapsed_seconds','tool_results']}),flush=True)
                save()
            finally:
                row=await get('/tasks/'+task_id)
                if row['status'] in ACTIVE:await post('/tasks/'+task_id+'/cancel')
        token='LocalPilot '+run_id+' ✓\n'
        await run_case('unicode_file_roundtrip',f'Use only file tools. Write exactly {json.dumps(token)} to {folder}/roundtrip.txt, read it back and verify it. Do not use terminal or desktop tools.',expected={folder+'/roundtrip.txt':token})
        expected={folder+'/batch/'+n+'.txt':v+'\n' for n,v in [('alpha','11'),('beta','22'),('gamma','33'),('delta','44')]}
        await run_case('multi_step_files',f'Use only file tools. Create these four files with the exact contents in this JSON mapping: {json.dumps(expected)}. Read back every file. Then write exactly "110\\n" (the sum of the four numbers, followed by a newline) to {folder}/sum.txt and read that back. Verify all five files. Do not use terminal or desktop tools.',expected={**expected,folder+'/sum.txt':'110\n'})
        for policy in ['reject','cancel']:
            marker=folder+'/'+policy+'-must-not-exist.txt'
            command='printf should-not-run > '+marker
            await run_case(policy+'_pending_command',f'Use terminal_execute to propose exactly this command, then wait for operator approval: {command}. Do not create files with any other tool.',policy=policy,absent=marker)
        report['final_readiness']=await get('/linux/status')
        report['passed']=all(c.get('passed') for c in report['cases']) and len(report['cases'])==4
        report['finished']=datetime.now(timezone.utc).isoformat();save()
        print(json.dumps({'passed':report['passed'],'evidence':str(output)}),flush=True)
        if not report['passed']:raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
