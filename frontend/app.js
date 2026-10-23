'use strict';

const $=id=>document.getElementById(id);

let booting=true, taskSelection=0;
let selected=null, source=null, cursor=0, reply='', polling=null,controlPolling=null,controlChanging=false;

let desktopControl={owner:'human',confirmed:false};

const terminalStates=new Set(['completed','failed','cancelled','interrupted','rejected']);

function notice(text=''){ $('notice').textContent=text;$('notice').hidden=!text; }

async function api(path,options={}){

 const response=await fetch(path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});

 if(response.status===401){signedOut();throw Error('Please sign in to continue.');}

 if(!response.ok){let data;try{data=await response.json()}catch{}throw Error(typeof data?.detail==='string'?data.detail:`Request failed (${response.status})`)}

 return response.json();

}

function signedOut(){source?.close();clearInterval(polling);clearInterval(controlPolling);$('workspace').hidden=true;$('login').hidden=false;$('signout').hidden=true;$('password').value='';window.dispatchEvent(new CustomEvent('localpilot-session',{detail:{signedIn:false}}));}

async function signedIn(){notice();$('login').hidden=true;$('workspace').hidden=false;$('signout').hidden=false;$('password').value='';window.dispatchEvent(new CustomEvent('localpilot-session',{detail:{signedIn:true}}));await refreshControl();clearInterval(controlPolling);controlPolling=setInterval(()=>refreshControl().catch(e=>notice(e.message)),2000);await history();const saved=localStorage.getItem('localpilot.task');if(saved)try{await selectTask(saved)}catch{localStorage.removeItem('localpilot.task')} }

async function history(){const tasks=await api('/tasks');$('recent').replaceChildren();if(!tasks.length){$('recent').textContent='No tasks yet.';return}for(const task of tasks){const button=document.createElement('button');button.textContent=`${task.request.slice(0,110)} · ${task.status.replaceAll('_',' ')}`;button.addEventListener('click',()=>selectTask(task.id).catch(e=>notice(e.message)));$('recent').append(button)}}

function addActivity(kind,data){if(kind!=='tool_result')return;if($('activity').querySelector('.muted'))$('activity').replaceChildren();const row=document.createElement('details'),title=document.createElement('summary'),body=document.createElement('pre');const labels={write_file:'Script saved',read_file:'Source verified',make_directory:'Directory created',list_files:'Workspace inspected',terminal_execute:'Command finished',package_plan:'Installation preview ready',package_install:'Installation checked',package_status:'Installation status checked',desktop_browser_open:'Website opened',desktop_observe:'Desktop observed',desktop_open_application:'Application opened',desktop_click:'Desktop clicked',desktop_type:'Text entered',desktop_keypress:'Key pressed',desktop_scroll:'Desktop scrolled',desktop_focus_window:'Window focused'};title.textContent=kind==='tool_started'?`Using ${data.tool.replaceAll('_',' ')}`:(data.result.ok?labels[data.tool]||'Step completed':'Step needs attention');if(data.result?.auto_approved)title.textContent='Routine command · auto-approved';body.textContent=JSON.stringify(kind==='tool_started'?data.arguments:data.result,null,2);row.append(title,body);if(kind==='tool_result'&&data.result.image_url){const link=document.createElement('a'),image=document.createElement('img');link.href=data.result.image_url;link.target='_blank';link.rel='noopener';image.src=data.result.image_url;image.alt='Observed Linux desktop';image.className='observation-image';link.append(image);row.append(link)}$('activity').append(row);while($('activity').childElementCount>60)$('activity').firstElementChild.remove();}

function setTask(task){selected=task;$('task-status').textContent=({awaiting_approval:'Waiting for approval',running:'Working in Linux',queued:'Queued',paused:'Paused - you control the desktop',completed:'Completed',failed:'Needs attention',cancelled:'Cancelled',rejected:'Command rejected',interrupted:'Interrupted — start a new task to continue'})[task.status]||task.status;$('task-request').textContent=task.request;$('task-request').hidden=true;$('approval').hidden=!task.approval;$('cancel').hidden=terminalStates.has(task.status);$('start').disabled=!terminalStates.has(task.status);$('request').readOnly=!terminalStates.has(task.status);if(task.approval){const gui=task.approval.tool.startsWith('desktop_'),install=task.approval.tool==='package_install';$('approval-title').textContent=install?'Review software installation':gui?'Review desktop action':'Review command';$('approval-description').textContent=install?'Installs these packages in Linux with administrator privileges. Once started, installation continues safely if you cancel the task or disconnect.':gui?'Controls the shared Linux desktop.':'Runs as pilot inside Linux.';if(install){const plan=task.approval.review;$('command').textContent='Requested: '+plan.requested.join(', ')+'\n'+(plan.actions.length?plan.actions.map(x=>x.package+'  '+x.version).join('\n'):'Already installed; no package changes needed.')+'\n\nNew packages only. No removal or upgrade.';}else if(gui){const {observation_id,...args}=task.approval.arguments;$('command').textContent=task.approval.tool.replaceAll('_',' ')+'\n'+JSON.stringify(args,null,2)}else $('command').textContent=task.approval.arguments.command;renderControl();}if(task.result){$('reply').textContent=task.result;$('reply').hidden=false}else{$('reply').textContent=reply;$('reply').hidden=!reply}if(terminalStates.has(task.status)){source?.close();clearInterval(polling);history().catch(()=>{})}}

async function refresh(){if(!selected)return;const id=selected.id,generation=taskSelection;const task=await api('/tasks/'+id);if(generation===taskSelection&&selected?.id===id)setTask(task)}

async function selectTask(id){
 const generation=++taskSelection;selected=null;

 source?.close();clearInterval(polling);cursor=0;reply='';$('reply').textContent='';$('reply').hidden=true;$('activity').replaceChildren();

 const task=await api('/tasks/'+id);if(generation!==taskSelection)return;selected=task;$('request').value=task.request;localStorage.setItem('localpilot.task',id);

 for(;;){const events=await api(`/tasks/${id}/events?after=${cursor}`);if(generation!==taskSelection)return;for(const event of events){cursor=event.id;if(event.kind==='token')reply+=event.data.text;else addActivity(event.kind,event.data)}if(events.length<500)break;}

 if(reply){$('reply').textContent=reply;$('reply').hidden=false}setTask(task);

 if(terminalStates.has(task.status))return;

 source=new EventSource(`/tasks/${id}/stream?after=${cursor}`);

 for(const kind of ['token','tool_started','tool_result','status','approval_requested'])source.addEventListener(kind,event=>{if(generation!==taskSelection||Number(event.lastEventId)<=cursor)return;cursor=Number(event.lastEventId);const data=JSON.parse(event.data);if(kind==='token'){reply+=data.text;$('reply').textContent=reply;$('reply').hidden=!reply}else if(kind==='tool_started'||kind==='tool_result')addActivity(kind,data);else refresh().catch(e=>notice(e.message))});

 source.onerror=()=>{if(selected&&!terminalStates.has(selected.status))$('connection').textContent='Reconnecting to task activity-'};source.onopen=()=>{$('connection').textContent='Private Linux workspace'};

 polling=setInterval(()=>refresh().catch(e=>notice(e.message)),3000);

}

function renderControl(){

 const human=desktopControl.owner==='human',blocked=controlChanging||!desktopControl.confirmed;

 $('control-status').textContent=blocked?'Confirming desktop control-':human?'You control the desktop - AI paused':'AI control enabled';

 $('take-control').hidden=human&&!blocked;$('resume-ai').hidden=!human||blocked;

 $('take-control').disabled=$('resume-ai').disabled=controlChanging;

 const manual=human&&!blocked;$('desktop-shield').hidden=manual;$('desktop-frame').inert=!manual;$('desktop-frame').tabIndex=manual?0:-1;

 if(!manual){try{$('desktop-frame').contentWindow?.blur()}catch{}}

 $('approve').disabled=controlChanging||human||!desktopControl.confirmed;

}

async function refreshControl(){desktopControl=await api('/desktop/state');renderControl();}

async function changeControl(owner){controlChanging=true;renderControl();try{desktopControl=await api('/desktop/control',{method:'POST',body:JSON.stringify({owner})});notice();}catch(e){notice(e.message);await refreshControl().catch(()=>{});throw e}finally{controlChanging=false;renderControl();}if(selected)await refresh();}

$('take-control').addEventListener('click',()=>changeControl('human').catch(()=>{}));

$('resume-ai').addEventListener('click',()=>changeControl('agent').catch(()=>{}));

$('desktop-only').addEventListener('click',async e=>{e.preventDefault();try{await changeControl('human');location.assign('/guacamole/')}catch{}});

$('login-form').addEventListener('submit',async e=>{e.preventDefault();if(booting)return;const button=e.submitter;button.disabled=true;try{await api('/session',{method:'POST',body:JSON.stringify({username:$('username').value,password:$('password').value})});await signedIn()}catch(error){notice(error.message)}finally{button.disabled=false}});

$('signout').addEventListener('click',async()=>{try{await api('/session',{method:'DELETE'});signedOut();notice()}catch(e){notice(e.message)}});

$('task-form').addEventListener('submit',async e=>{e.preventDefault();$('start').disabled=true;notice();try{const task=await api('/tasks',{method:'POST',body:JSON.stringify({request:$('request').value})});await selectTask(task.id)}catch(e){notice(e.message);$('start').disabled=false}});

async function decide(allow){if(!selected?.approval)return;$('approve').disabled=$('reject').disabled=true;try{await api(`/tasks/${selected.id}/approval`,{method:'POST',body:JSON.stringify({approval_id:selected.approval.id,allow})});await refresh()}catch(e){notice(e.message)}finally{$('reject').disabled=false;renderControl();}}

$('approve').addEventListener('click',()=>decide(true));$('reject').addEventListener('click',()=>decide(false));$('cancel').addEventListener('click',async()=>{if(!selected)return;try{await api(`/tasks/${selected.id}/cancel`,{method:'POST'});await refresh()}catch(e){notice(e.message)}});

function tab(desktop){$('agent-view').hidden=desktop;$('desktop-view').hidden=!desktop;document.querySelector('.shell').classList.toggle('desktop-mode',desktop);for(const [id,on]of [['agent-tab',!desktop],['desktop-tab',desktop]]){$(id).classList.toggle('selected',on);$(id).setAttribute('aria-pressed',String(on))}if(desktop&&!$('desktop-frame').src)$('desktop-frame').src=$('desktop-frame').dataset.src;}

$('agent-tab').addEventListener('click',()=>tab(false));$('desktop-tab').addEventListener('click',()=>tab(true));

api('/health').then(signedIn).catch(()=>{signedOut();notice()}).finally(()=>{booting=false;for(const field of document.querySelectorAll('#login-form input,#login-form button'))field.disabled=false;});
