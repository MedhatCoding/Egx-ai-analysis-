const CACHE_NAME='gpt-mi-pwa-v12';
const APP_SHELL=['./','./index.html','./manifest.webmanifest','./icons/gpt-mi.svg?v=12'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(APP_SHELL)))});
self.addEventListener('message',event=>{if(event.data&&event.data.type==='SKIP_WAITING')self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(key=>key.startsWith('gpt-mi-pwa-')&&key!==CACHE_NAME).map(key=>caches.delete(key)));await self.clients.claim()})())});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin)return;
 if(request.mode==='navigate'){
  event.respondWith((async()=>{try{return await fetch(request,{cache:'no-store'})}catch(error){return (await caches.match('./index.html'))||(await caches.match('./'))}})());return;
 }
 if(APP_SHELL.some(path=>new URL(path,self.location.href).pathname===url.pathname)){
  event.respondWith((async()=>{const cached=await caches.match(request);const network=fetch(request,{cache:'no-store'}).then(response=>{if(response&&response.ok)caches.open(CACHE_NAME).then(cache=>cache.put(request,response.clone()));return response}).catch(()=>null);return cached||await network||Response.error()})());
 }
});