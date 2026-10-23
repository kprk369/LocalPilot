"use strict";
const CACHE='localpilot-public-v1';
const PUBLIC=['/assets/offline.html','/assets/offline.css','/assets/offline.js','/assets/icons/icon-192.png','/assets/icons/icon-512.png','/assets/icons/apple-touch-icon.png','/assets/icons/maskable-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(PUBLIC)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('localpilot-public-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);if(url.origin!==self.location.origin||event.request.method!=='GET')return;
 if(event.request.mode==='navigate'&&url.pathname==='/'){
  event.respondWith(fetch(event.request).then(response=>response.status>=500?caches.match('/assets/offline.html'):response).catch(()=>caches.match('/assets/offline.html')));return;
 }
 if(PUBLIC.includes(url.pathname)&&url.search==='')event.respondWith(caches.open(CACHE).then(async cache=>(await cache.match(event.request))||fetch(event.request)));
 // No API responses, passwords, screenshots, task data, desktop traffic, or writes are cached or queued.
});
