const CACHE = 'fairprice-original-v12-sms-recipients';
const SHELL = ['/', '/static/style.css', '/static/design.css', '/static/flow.js'];
SHELL.push(...['english.png','swahili.png','logo-white.png','logo-green.png'].map(n=>'/assets/design/'+n));
const PHOTOS = ['beans','maize','sorghum','millet','cassava_fresh','leafy_vegetables'].map(c=>`/assets/${c}.png`);
PHOTOS.push(...['beans','maize','sorghum','millet','cassava_fresh','leafy_vegetables'].map(c=>`/assets/grades/${c}.png`));
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('fairprice-original-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
// Install the small shell first. Photos are cached as used, not all downloaded on setup.
// API records use explicit dated localStorage entries in flow.js.
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
  if(PHOTOS.includes(url.pathname)){
    event.respondWith(caches.match(event.request).then(saved=>saved||fetch(event.request).then(response=>{
      if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
      return response;
    })));
    return;
  }
  if(!SHELL.includes(url.pathname))return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
    return response;
  }).catch(()=>caches.match(event.request)));
});
