// DOM integration checks, not a rendered-browser or real-device acceptance test.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const base=process.env.FAIRPRICE_TEST_URL||'http://127.0.0.1:8000';
const dom=new JSDOM(fs.readFileSync('frontend/index.html','utf8'),{url:base,runScripts:'outside-only'});
const w=dom.window,d=w.document;
let offline=false;
w.fetch=(url,options)=>offline?Promise.reject(Error('offline')):fetch(new URL(url,base),options);
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(){this.open=false;};
w.eval(fs.readFileSync('frontend/src/app.js','utf8'));
const click=selector=>{assert.ok(d.querySelector(selector),`Missing ${selector}`);d.querySelector(selector).click();};
const wait=async check=>{for(let i=0;i<100;i++){if(check())return;await new Promise(r=>setTimeout(r,30));}throw Error('Timed out waiting for UI');};
async function main(){
  await wait(()=>d.querySelector('[data-lang="en"]'));
  click('[data-lang="en"]');click('[data-category="grains"]');
  assert.equal(d.querySelectorAll('.crop-row').length,4);
  const search=d.querySelector('#search');search.value='maize';search.dispatchEvent(new w.Event('input'));
  assert.equal(d.querySelectorAll('.crop-row').length,1);
  search.value='unsupported mango';search.dispatchEvent(new w.Event('input'));
  assert.ok(d.querySelector('.empty'));
  click('[data-back="categories"]');
  const catalog=await (await fetch(base+'/api/crops')).json();
  for(const crop of catalog.crops){
    click(`[data-category="${crop.category}"]`);click(`[data-crop="${crop.id}"]`);
    await wait(()=>d.querySelector('.detail-top h1')?.textContent===crop.name);
    assert.equal(d.querySelectorAll('.grade').length,3);
    assert.equal(d.querySelector('.detail-top img').getAttribute('src'),crop.image);
    assert.ok(crop.image.endsWith('.png'));
    const market=d.querySelector('#market');market.selectedIndex=market.options.length-1;
    market.dispatchEvent(new w.Event('change'));
    const selected=market.value;
    const row=(await(await fetch(base+`/api/prices/${crop.id}?market=${encodeURIComponent(selected)}`)).json()).rows[0];
    assert.ok(d.querySelector('.source-strip').textContent.includes(row.last_month));
    for(const [i,g] of ['A','B','C'].entries()){
      assert.equal(d.querySelectorAll('.grade .price')[i].textContent,new Intl.NumberFormat('en-UG').format(row.grade_prices[g]));
    }
    click('[data-sms-grade="C"]');
    await wait(()=>d.querySelector('#sms-message').textContent.includes(`C: UGX ${row.grade_prices.C}/kg`));
    assert.ok(d.querySelector('#sms-message').textContent.includes(row.last_month));
    click('.close');click('[data-back="list"]');click('[data-back="categories"]');
  }
  click('#language');assert.equal(d.documentElement.lang,'sw');
  click('[data-category="grains"]');click('[data-crop="beans"]');
  await wait(()=>d.querySelector('.detail-top h1')?.textContent==='Maharagwe');
  click('#language');assert.equal(d.querySelector('.detail-top h1').textContent,'Beans');
  click('#training-open');await wait(()=>d.querySelector('.training-table'));assert.equal(d.querySelectorAll('.training-table tbody tr').length,6);click('.close');
  offline=true;click('#refresh');await wait(()=>d.querySelector('#connection').textContent.includes('Saved data'));
  assert.equal(d.querySelectorAll('.grade').length,3);
  offline=false;
  click('.brand');assert.ok(d.querySelector('[data-lang="en"]'));
  console.log('PASS: all six crop journeys; search; market changes; A/B/C values; SMS parity; back/home navigation; language toggle; training panel; saved-record offline fallback.');
  console.log('DOM checks only: visual layout, device speech and service-worker reload are not verified here.');
  dom.window.close();
}
main().catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
