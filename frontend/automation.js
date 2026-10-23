"use strict";
(()=>{
 const toggle=document.getElementById('routine-commands'),status=document.getElementById('automation-status');
 let generation=0,active=false;
 async function request(method='GET',body){
  const response=await fetch('/settings/automation',{method,credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  if(!response.ok)throw Error('Could not confirm auto-approval. Please try again.');
  return response.json();
 }
 async function load(){const token=generation;toggle.disabled=true;try{const value=await request();if(token!==generation)return;toggle.checked=value.routine_commands;status.textContent=value.routine_commands?'On — routine commands run automatically.':'Off — commands wait for review.';toggle.disabled=false;return true}catch(error){if(token===generation)status.textContent=error.message;return false}}
 window.addEventListener('localpilot-session',event=>{generation++;active=event.detail.signedIn;toggle.checked=false;toggle.disabled=true;status.textContent='';if(active)load()});
 toggle.addEventListener('change',async()=>{const token=generation,value=toggle.checked;toggle.disabled=true;status.textContent='Saving…';try{const saved=await request('POST',{routine_commands:value});if(token!==generation)return;toggle.checked=saved.routine_commands;status.textContent=saved.routine_commands?'On — routine commands run automatically.':'Off — commands wait for review.';toggle.disabled=false}catch(error){if(token===generation){status.textContent=error.message;await load()}}});
 if(!document.getElementById('workspace').hidden){active=true;load()}
})();
