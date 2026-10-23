"use strict";
(()=>{
 const button=document.getElementById('install-app'),dialog=document.getElementById('install-dialog');
 const display=matchMedia('(display-mode: standalone)');let promptEvent=null;
 const installed=()=>display.matches||navigator.standalone===true;
 const update=()=>{button.hidden=installed();if(installed()&&dialog.open)dialog.close()};
 const ios=()=>/iPhone|iPad|iPod/.test(navigator.userAgent)||(/Macintosh/.test(navigator.userAgent)&&navigator.maxTouchPoints>1);
 const showInstructions=()=>{
  const steps=ios()?['Open this page in Safari and tap Share.','Choose Add to Home Screen.','Keep Open as Web App enabled if shown, then tap Add.']:/Android/.test(navigator.userAgent)?['Open the browser menu.','Choose Install app or Add to Home screen.','Confirm to add LocalPilot.']:['Open your browser menu or the install icon in the address bar.','Choose Install LocalPilot or Install this site as an app.','Confirm to add LocalPilot.'];
  const list=document.getElementById('install-steps');list.replaceChildren();for(const text of steps){const item=document.createElement('li');item.textContent=text;list.append(item)}dialog.showModal();
 };
 button.addEventListener('click',async()=>{if(promptEvent){const event=promptEvent;promptEvent=null;try{await event.prompt();await event.userChoice}catch{showInstructions()}}else showInstructions()});
 document.getElementById('install-close').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close()}});
 window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();promptEvent=event;update()});window.addEventListener('appinstalled',()=>{promptEvent=null;button.hidden=true});display.addEventListener('change',update);update();
 if('serviceWorker' in navigator&&window.isSecureContext){navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).catch(()=>{document.getElementById('install-intro').textContent='You can add LocalPilot to your Home Screen. Offline guidance is currently unavailable.'})}
})();
