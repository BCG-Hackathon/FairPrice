// DOM integration checks against the running backend, separate from browser acceptance.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const base=process.env.FAIRPRICE_TEST_URL||'http://127.0.0.1:8000';
const dom=new JSDOM(fs.readFileSync('frontend/index.html','utf8'),{url:base,runScripts:'outside-only'});
const w=dom.window,d=w.document;
let offline=false,tick,clock=Date.now(),rejectCrop=false;
w.fetch=(url,options)=>rejectCrop&&url.includes('/api/prices/')?Promise.resolve({ok:false,status:404}):offline?Promise.reject(Error('offline')):fetch(new URL(url,base),options);
w.Date.now=()=>clock;w.setInterval=fn=>{tick=fn;};w.scrollTo=()=>{};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
w.eval(fs.readFileSync('frontend/src/flow.js','utf8'));
const click=s=>{assert.ok(d.querySelector(s),`Missing ${s}`);d.querySelector(s).click();};
const wait=async check=>{for(let i=0;i<100;i++){if(check())return;await new Promise(r=>setTimeout(r,30));}throw Error('Timed out waiting for UI');};
async function main(){
  await wait(()=>d.querySelector('[data-lang="en"]'));
  assert.equal(d.querySelector('#sms-open'),null);assert.equal(d.querySelector('#training-open'),null);
  click('[data-lang="en"]');click('[data-category="grains"]');assert.equal(d.querySelectorAll('.crop-row').length,4);
  const search=d.querySelector('#search');search.value='mango';search.dispatchEvent(new w.Event('input'));assert.ok(d.querySelector('.empty'));click('[data-back="categories"]');
  const catalog=await(await fetch(base+'/api/crops')).json();
  for(const crop of catalog.crops){
    click(`[data-category="${crop.category}"]`);click(`[data-crop="${crop.id}"]`);await wait(()=>d.querySelector('#view-price'));
    const select=d.querySelector('#market');select.selectedIndex=select.options.length-1;select.dispatchEvent(new w.Event('change'));
    const market=select.value;click('#view-price');
    assert.equal(d.querySelector('.detail-top h1').textContent,crop.name);
    assert.equal(d.querySelectorAll('.grade').length,3);assert.equal(d.querySelectorAll('.grade img').length,0);
    assert.equal(d.querySelector('.detail-top img').getAttribute('src'),crop.image);
    const row=(await(await fetch(base+`/api/prices/${crop.id}?market=${encodeURIComponent(market)}`)).json()).rows[0];
    assert.ok(d.querySelector('.base-price strong').textContent.includes(new Intl.NumberFormat('en-UG').format(row.market_price)));
    for(const[i,g]of['A','B','C'].entries())assert.equal(d.querySelectorAll('.grade .price')[i].textContent,new Intl.NumberFormat('en-UG').format(row.grade_prices[g]));
    assert.equal(d.querySelector('.calculation').open,false);assert.equal(d.querySelector('.grade-details').open,false);
    click('#send-sms');assert.ok(d.querySelector('#modal-content').textContent.includes('not available'));assert.equal(d.querySelector('input[type=tel]'),null);click('.close');
    click('#compare-open');assert.equal(d.querySelectorAll('tbody tr').length,crop.markets.length);assert.ok(d.querySelector('#modal-content').textContent.includes('Transport costs are not included'));click('.close');
    click('[data-back="market"]');click('[data-back="list"]');click('[data-back="categories"]');
  }
  click('[data-category="grains"]');click('[data-crop="beans"]');await wait(()=>d.querySelector('#view-price'));d.querySelector('#market').value='Lira';d.querySelector('#market').dispatchEvent(new w.Event('change'));click('#view-price');
  assert.ok(d.querySelector('.notice').textContent.includes('No recent price'));
  click('#language');assert.equal(d.documentElement.lang,'sw');click('#language');
  offline=true;click('#refresh');await wait(()=>d.querySelector('#connection').textContent.includes('saved records'));assert.ok(d.querySelector('.base-price'));offline=false;
  rejectCrop=true;click('#refresh');await wait(()=>d.querySelector('#modal-content h2'));assert.ok(d.querySelector('#modal-content').textContent.includes('Price unavailable'));assert.equal(w.localStorage.getItem('fairprice:/api/prices/beans'),null);rejectCrop=false;click('.close');
  click('#staff-open');assert.ok(d.querySelector('#setup-form'));click('#training-open');await wait(()=>d.querySelector('.training-table'));assert.equal(d.querySelectorAll('.training-table tbody tr').length,6);click('.close');
  click('#sms-open');await wait(()=>d.querySelector('#sms-message').textContent.includes('Recorded'));assert.ok(d.querySelector('#modal-content').textContent.includes('test only'));click('.close');
  d.querySelector('#kiosk-name').value='Gulu kiosk';d.querySelector('#default-market').value='Gulu';d.querySelector('#setup-form').dispatchEvent(new w.Event('submit',{cancelable:true}));assert.ok(w.localStorage.getItem('fairprice:setup').includes('Gulu kiosk'));
  click('#start-over');click('[data-lang="en"]');click('[data-category="grains"]');click('[data-crop="maize"]');await wait(()=>d.querySelector('#view-price'));assert.equal(d.querySelector('#market').value,'Gulu');
  clock+=105001;tick();assert.equal(d.querySelector('#idle-notice').hidden,false);clock+=15000;tick();assert.ok(d.querySelector('[data-lang="en"]'));assert.equal(d.querySelector('#modal').open,false);assert.equal(d.querySelector('#market'),null);
  console.log('PASS: six crop-market-price flows; grade policy; old-data warning; comparison; farmer SMS unavailable/no phone collection; staff tools; offline fallback; 404 invalidates cache; device setup; idle warning/reset.');
  dom.window.close();
}
main().catch(e=>{console.error(e);dom.window.close();process.exitCode=1;});
