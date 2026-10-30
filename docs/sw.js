const CACHE_NAME='gpt-mi-pwa-v11';
const APP_SHELL=['./','./index.html','./manifest.webmanifest','./icons/gpt-mi.svg?v=11','./data/latest.json'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(APP_SHELL)))});
self.addEventListener('message',event=>{if(event.data&&event.data.type==='SKIP_WAITING')self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(key=>key.startsWith('gpt-mi-pwa-')&&key!==CACHE_NAME).map(key=>caches.delete(key)));await self.clients.claim()})())});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin)return;
 if(url.pathname.endsWith('/data/latest.json')){
  event.respondWith((async()=>{const cache=await caches.open(CACHE_NAME);try{const response=await fetch(request,{cache:'no-store'});if(response&&response.ok){await cache.put('./data/latest.json',response.clone());return response}}catch(error){}return (await cache.match('./data/latest.json'))||Response.error()})());return;
 }
 if(request.mode==='navigate'){
  event.respondWith((async()=>{try{const response=await fetch(request,{cache:'no-store'});if(response&&response.ok){const cache=await caches.open(CACHE_NAME);cache.put('./index.html',response.clone())}return response}catch(error){return (await caches.match('./index.html'))||(await caches.match('./'))}})());return;
 }
 if(APP_SHELL.some(path=>new URL(path,self.location.href).pathname===url.pathname)){
  event.respondWith((async()=>{const cached=await caches.match(request);const network=fetch(request).then(response=>{if(response&&response.ok)caches.open(CACHE_NAME).then(cache=>cache.put(request,response.clone()));return response}).catch(()=>null);return cached||await network||Response.error()})());
 }
});