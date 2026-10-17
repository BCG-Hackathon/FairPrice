const CACHE = 'fairprice-original-v2-photos';
const SHELL = ['/', '/static/style.css', '/static/app.js', ...['beans','maize','sorghum','millet','cassava_fresh','leafy_vegetables'].map(c=>`/assets/${c}.png`)];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('fairprice-original-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
// Cache only this app's shell. API records use explicit dated localStorage entries in app.js.
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin||!SHELL.includes(url.pathname))return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
    return response;
  }).catch(()=>caches.match(event.request)));
});
