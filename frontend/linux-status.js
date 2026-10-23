"use strict";
(()=>{
 const status=document.getElementById('linux-status'),label=document.getElementById('linux-status-label');
 let timer=null,generation=0,request=null;
 const set=(state,text,message)=>{status.dataset.state=state;label.textContent=text;status.title=message};
 const stop=()=>{generation++;clearInterval(timer);timer=null;if(request)request.abort();request=null;status.hidden=true};
 const check=async(token)=>{
  if(token!==generation||status.hidden||request)return;
  if(!navigator.onLine){set('offline','Linux offline','Your device is offline. Reconnect to check Linux.');return}
  const controller=new AbortController();request=controller;const timeout=setTimeout(()=>controller.abort(),10000);
  try{
   const response=await fetch('/linux/status',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if(token!==generation)return;if(response.status===401){stop();return}if(!response.ok)throw Error('Readiness check unavailable');
   const result=await response.json();if(token!==generation)return;
   const labels={ready:'Linux ready',desktop_disconnected:'Linux connected',attention:'Linux needs attention',offline:'Linux offline'};
   const state=labels[result.state]?result.state:'offline';
   set(state,labels[state],result.message+' Checked '+new Date(result.checked_at*1000).toLocaleTimeString()+'.');
  }catch(error){if(token===generation&&!status.hidden)set('offline','Linux offline','Cannot verify the Linux connection. Check your network and laptop.');}
  finally{clearTimeout(timeout);if(request===controller)request=null}
 };
 const start=()=>{stop();status.hidden=false;set('checking','Checking Linux','Checking the VM connection and shared desktop.');const token=generation;check(token);timer=setInterval(()=>check(token),15000)};
 window.addEventListener('localpilot-session',event=>event.detail.signedIn?start():stop());
 window.addEventListener('offline',()=>{if(!status.hidden){if(request)request.abort();set('offline','Linux offline','Your device is offline. Reconnect to check Linux.')}});
 window.addEventListener('online',()=>{if(!status.hidden)check(generation)});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!status.hidden)check(generation)});
 if(!document.getElementById('workspace').hidden)start();
})();
