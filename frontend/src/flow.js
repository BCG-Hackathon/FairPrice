const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const DEFAULTS={name:'Community kiosk',market:'',language:'en',idleMinutes:2};
let setup={...DEFAULTS};
try{const saved=JSON.parse(localStorage.getItem('fairprice:setup'));if(saved)setup={...setup,...saved};}catch{}
if(!['en','sw'].includes(setup.language))setup.language='en';
if(![2,3,5].includes(Number(setup.idleMinutes)))setup.idleMinutes=2;
const state={lang:setup.language,screen:'welcome',category:null,crop:null,market:null,catalog:null,prices:null,status:null,staffData:null};
let navigationVersion=0,lastActivity=Date.now(),offlineRecord=false;
const text=(en,sw)=>state.lang==='sw'?sw:en;
const cropName=c=>state.lang==='sw'?c.name_sw:c.name;
const money=p=>new Intl.NumberFormat('en-UG').format(p);
const image=c=>`<img src="${esc(c.image)}" alt="${esc(cropName(c))}" loading="lazy" decoding="async">`;
const month=m=>{const [y,n]=m.split('-').map(Number);return new Intl.DateTimeFormat(state.lang==='sw'?'sw':'en-GB',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(y,n-1,1)));};
function setConnection(message){$('#connection').textContent=message;}
async function api(path){
  let response;
  try{response=await fetch(path);}catch{response=null;}
  // Missing/invalid records must not be disguised by an old cached success.
  if(response && !response.ok && response.status<500){try{localStorage.removeItem('fairprice:'+path);}catch{}throw Error('Record unavailable');}
  if(response?.ok){const data=await response.json();try{localStorage.setItem('fairprice:'+path,JSON.stringify({data,saved:new Date().toISOString()}));}catch{}offlineRecord=false;setConnection('');return data;}
  let saved;try{saved=JSON.parse(localStorage.getItem('fairprice:'+path));}catch{}
  if(!saved)throw Error('No saved data');
  offlineRecord=true;setConnection(text('Offline or service unavailable · showing saved records. Recorded dates still apply.','Hakuna muunganisho au huduma haipatikani · tunaonyesha taarifa zilizohifadhiwa. Tarehe za kumbukumbu bado zinatumika.'));
  return saved.data;
}
function closeModal(){if($('#modal').open)$('#modal').close();$('#modal-content').replaceChildren();}
function showModal(html){closeModal();$('#modal-content').innerHTML=html;$('#modal').showModal();$('#modal').scrollTop=0;}
function go(screen){navigationVersion++;state.screen=screen;render();window.scrollTo?.(0,0);}
function resetSession(){navigationVersion++;closeModal();if('speechSynthesis'in window)speechSynthesis.cancel();Object.assign(state,{lang:setup.language,screen:'welcome',category:null,crop:null,market:null,prices:null});lastActivity=Date.now();$('#idle-notice').hidden=true;render();window.scrollTo?.(0,0);}
function touch(){lastActivity=Date.now();$('#idle-notice').hidden=true;}
['pointerdown','click','keydown','input','change'].forEach(type=>document.addEventListener(type,touch,{passive:true}));
setInterval(()=>{
  if(state.screen==='welcome')return;
  const left=Number(setup.idleMinutes)*60000-(Date.now()-lastActivity);
  if(left<=0){resetSession();return;}
  if(left<=15000){$('#idle-notice').hidden=false;$('#idle-notice').innerHTML=`${text('Returning to the start in','Kurudi mwanzo baada ya')} ${Math.ceil(left/1000)} ${text('seconds','sekunde')}. <button id="keep-going">${text('Keep using','Endelea')}</button>`;}
},1000);
function render(){
  document.documentElement.lang=state.lang;
  $('#language').textContent=text('English / Kiswahili','Kiswahili / English');
  $('#start-over').textContent=text('Start again','Anza tena');
  $('#staff-open').textContent=text('Kiosk staff','Wahudumu wa kioski');
  $('#footer-copy').textContent=text('No account needed · Dated reference prices, not guaranteed offers','Huhitaji akaunti · Bei za kumbukumbu, si ofa zilizohakikishwa');
  if(!state.catalog)return;
  if(state.screen==='welcome'){
    $('#app').innerHTML=`<div class="intro"><h1>${text('Know your crop’s value.','Fahamu thamani ya mazao yako.')}</h1><p>${text('Check a market price before you sell. No account or phone needed.','Angalia bei ya soko kabla ya kuuza. Huhitaji akaunti au simu.')}</p><h2>${text('Choose your language','Chagua lugha')}</h2><div class="big-actions"><button class="primary" data-lang="en">English</button><button data-lang="sw">Kiswahili</button></div><p class="muted">${esc(setup.name)}</p></div>`;
  }else if(state.screen==='categories'){
    $('#app').innerHTML=`<button class="back" data-back="welcome">← ${text('Language','Lugha')}</button><div class="intro"><h1>${text('What do you grow?','Unalima nini?')}</h1><p>${text('Choose your crop category.','Chagua aina ya mazao.')}</p></div><div class="big-actions"><button class="category" data-category="grains"><img src="/assets/maize.png" alt="">${text('Grains & beans','Nafaka na maharagwe')}</button><button class="category" data-category="vegetables"><img src="/assets/cassava_fresh.png" alt="">${text('Vegetables & roots','Mboga na mizizi')}</button></div>`;
  }else if(state.screen==='list'){
    $('#app').innerHTML=`<button class="back" data-back="categories">← ${text('Categories','Aina za mazao')}</button><div class="list-head"><h1>${state.category==='grains'?text('Grains & beans','Nafaka na maharagwe'):text('Vegetables & roots','Mboga na mizizi')}</h1><input id="search" type="search" aria-label="${text('Search crops','Tafuta mazao')}" placeholder="${text('Search crops…','Tafuta mazao…')}"></div><div id="crop-list" class="crop-list"></div>`;renderList('');$('#search').oninput=e=>renderList(e.target.value);
  }else if(state.screen==='market')renderMarket();
  else if(state.screen==='detail')renderDetail();
  else if(state.screen==='staff')renderStaff();
}
function renderList(query){const list=state.catalog.crops.filter(c=>c.category===state.category&&`${c.name} ${c.name_sw}`.toLowerCase().includes(query.toLowerCase()));$('#crop-list').innerHTML=list.map(c=>`<button class="crop-row" data-crop="${c.id}">${image(c)}<span><strong>${esc(cropName(c))}</strong><small>${esc(c.form)}</small></span><span class="arrow" aria-hidden="true">›</span></button>`).join('')||`<p class="empty">${text('No matching crop with available data.','Hakuna zao lenye taarifa linalolingana.')}</p>`;}
async function openCrop(id,market=null,refresh=false){
  const version=++navigationVersion;
  try{const data=await api('/api/prices/'+encodeURIComponent(id));if(version!==navigationVersion)return;if(!data.rows?.length)throw Error();
    state.prices=data;state.crop=id;state.market=[market,setup.market].find(m=>data.rows.some(r=>r.market===m))||data.rows[0].market;state.screen=refresh?'detail':'market';render();window.scrollTo?.(0,0);
  }catch{if(version===navigationVersion)showModal(`<h2>${text('Price unavailable','Bei haipatikani')}</h2><p>${text('No published or saved price is available for this crop. Reconnect and try again, or choose another crop.','Hakuna bei iliyochapishwa au kuhifadhiwa kwa zao hili. Unganisha tena au chagua zao jingine.')}</p>`);}
}
function marketOptions(){return state.prices.rows.map(r=>`<option value="${esc(r.market)}" ${r.market===state.market?'selected':''}>${esc(r.market)} · ${r.last_month}</option>`).join('');}
function renderMarket(){
  const crop=state.catalog.crops.find(c=>c.id===state.crop);
  $('#app').innerHTML=`<button class="back" data-back="list">← ${text('Crops','Mazao')}</button><div class="detail-top">${image(crop)}<div><h1>${text('Which market?','Soko gani?')}</h1><p>${esc(cropName(crop))} · UGX/kg</p></div></div><div class="market-step"><label for="market">${text('Choose a market','Chagua soko')}</label><select id="market">${marketOptions()}</select><p class="muted">${text('The date beside each market tells you when its price was recorded.','Tarehe iliyo karibu na soko inaonyesha mwezi ambao bei ilirekodiwa.')}</p><button class="primary" id="view-price">${text('See the price','Ona bei')}</button></div>`;
  $('#market').onchange=e=>state.market=e.target.value;$('#view-price').onclick=()=>go('detail');
}
function current(){return state.prices?.rows.find(r=>r.market===state.market);}
function renderDetail(){
  const crop=state.catalog.crops.find(c=>c.id===state.crop),row=current();if(!row){go('market');return;}
  const old=row.stale;
  $('#app').innerHTML=`<button class="back" data-back="market">← ${text('Change market','Badilisha soko')}</button><div class="detail-top">${image(crop)}<div><h1>${esc(cropName(crop))}</h1><p>${esc(row.market)} · ${esc(crop.form)}</p></div></div>
    <p class="record-date">${text('Recorded','Ilirekodiwa')}: <strong>${month(row.last_month)}</strong> · WFP / HDX</p>
    ${old?`<div class="notice"><strong>${text('No recent price available for this market.','Hakuna bei ya hivi karibuni kwa soko hili.')}</strong> ${text('The older reference below is over six months old.','Bei ya kumbukumbu hapa chini ina zaidi ya miezi sita.')}</div>`:''}
    <section class="base-price"><span>${old?text('Older market reference','Bei ya zamani ya kumbukumbu'):text('Market reference price','Bei ya kumbukumbu ya soko')}</span><strong>UGX ${money(row.market_price)} <small>/ kg</small></strong><p>${row.price_status==='observed wholesale'?text('Published wholesale price.','Bei ya jumla iliyochapishwa.'):text('Estimated wholesale price from a published shop price.','Makadirio ya bei ya jumla kutoka bei ya rejareja iliyochapishwa.')}</p></section>
    <p class="price-caution">${text('A dated guide for negotiation—not a live buyer offer or a guaranteed selling price.','Mwongozo wa bei wenye tarehe, si ofa ya mnunuzi ya sasa au bei iliyohakikishwa.')}</p>
    <details class="grade-details"><summary>${text('See A / B / C price adjustments','Ona marekebisho ya bei A / B / C')}</summary><p>${text('These are indicative price adjustments. They do not identify or certify the quality of your crop.','Haya ni makadirio ya marekebisho ya bei. Hayatambui wala kuthibitisha ubora wa zao lako.')}</p><div class="grades">${['A','B','C'].map((g,i)=>`<section class="grade"><h2>${text('Grade','Daraja')} ${g}</h2><div class="price">${money(row.grade_prices[g])}</div><div class="unit">UGX / kg</div><p>${['+4%',text('Base price','Bei ya msingi'),'−5.5%'][i]}</p></section>`).join('')}</div></details>
    <div class="detail-actions"><button class="primary" id="read-aloud">${text('Read aloud','Soma kwa sauti')}</button><button id="send-sms">${text('Send this price by SMS','Tuma bei hii kwa SMS')}</button><button id="compare-open">${text('Compare markets','Linganisha masoko')}</button></div>
    <details class="quality"><summary>${text('How do I check crop quality?','Ninaangaliaje ubora wa zao?')}</summary><p>${text('This app has not inspected your produce. A photo alone cannot establish an official grade. The A/B/C pricing labels have not been mapped to verified crop standards.','Programu hii haijakagua mazao yako. Picha pekee haiwezi kuthibitisha daraja rasmi. Lebo za bei A/B/C hazijaunganishwa na viwango vya mazao vilivyothibitishwa.')}</p>${crop.id==='beans'?`<p>${text('UNBS bean guidance considers foreign matter, damaged and broken beans, and measured moisture. Its grades 1/2/3 are separate from our A/B/C price adjustments.','Mwongozo wa UNBS wa maharagwe huangalia uchafu, maharagwe yaliyoharibika au kuvunjika na unyevu unaopimwa. Madaraja yake 1/2/3 ni tofauti na marekebisho yetu ya bei A/B/C.')}</p><a href="https://webstore.unbs.go.ug/standards/DRY_BEANS_-_BEST_PRACTICES_FOR_IMPROVED_NUTRITION_AND_INCOMES.pdf" target="_blank" rel="noreferrer">${text('UNBS dry-bean guidance','Mwongozo wa UNBS wa maharagwe makavu')}</a>`:`<p>${text('Verified guidance for this crop is not available in the app yet. Ask a trained local produce grader before treating a price adjustment as a quality grade.','Mwongozo uliothibitishwa wa zao hili haupo kwenye programu bado. Muulize mkaguzi wa mazao aliyefunzwa kabla ya kutumia marekebisho ya bei kama daraja la ubora.')}</p>`}</details>
    <details class="calculation"><summary>${text('Where does this price come from?','Bei hii imetoka wapi?')}</summary><div class="source-strip">${text('Published observation','Bei iliyochapishwa')}: UGX ${money(row.observed_price)}/kg (${esc(row.observed_price_type)})<br>${text('Wholesale conversion','Ubadilishaji hadi bei ya jumla')}: × ${row.market_factor} · ${esc(row.market_factor_basis)}<br>${text('A +4%, B base, C −5.5% are application assumptions, not verified UNBS price rules.','A +4%, B bei ya msingi, C −5.5% ni dhana za programu, si kanuni za bei za UNBS zilizothibitishwa.')}<br><a href="https://data.humdata.org/dataset/wfp-food-prices-for-uganda" target="_blank" rel="noreferrer">WFP / HDX</a></div></details>
    <button class="back" id="refresh">${text('Check for an updated record','Angalia taarifa mpya')}</button>`;
  $('#read-aloud').onclick=()=>readPrice(crop,row);$('#send-sms').onclick=smsUnavailable;$('#compare-open').onclick=compareDialog;$('#refresh').onclick=()=>openCrop(state.crop,state.market,true);
}
function smsUnavailable(){showModal(`<h2>${text('SMS is not available yet','SMS haipatikani bado')}</h2><p>${text('This kiosk cannot send a real text message yet. No phone number is needed or collected. You can read the price aloud or write down the crop, market, price and recorded month.','Kioski hiki hakiwezi kutuma ujumbe halisi bado. Hatuhitaji wala kukusanya nambari ya simu. Unaweza kusikiliza bei au kuandika zao, soko, bei na mwezi wa kumbukumbu.')}</p><p class="form-note">${text('The SMS test panel is available in the staff view.','Paneli ya majaribio ya SMS ipo kwenye sehemu ya wahudumu.')}</p>`);}
function readPrice(crop,row){
  if(!('speechSynthesis'in window)){showModal(`<h2>${text('Read aloud unavailable','Sauti haipatikani')}</h2><p>${text('Ask the kiosk attendant to read the displayed price.','Muombe mhudumu asome bei iliyoonyeshwa.')}</p>`);return;}
  if(state.lang==='sw'&&!speechSynthesis.getVoices().some(v=>v.lang.toLowerCase().startsWith('sw'))){showModal('<h2>Sauti ya Kiswahili haipatikani</h2><p>Muombe mhudumu asome bei iliyoonyeshwa. Kifaa hiki hakina sauti ya Kiswahili inayopatikana.</p>');return;}
  const utterance=new SpeechSynthesisUtterance(text(`${crop.name}. ${row.market}. Recorded ${month(row.last_month)}. Reference price ${row.market_price} Ugandan shillings per kilogram. ${row.stale?'This record is over six months old.':''} Not a current buyer offer.`,`${crop.name_sw}. ${row.market}. ${month(row.last_month)}. Bei ya kumbukumbu ${row.market_price} shilingi za Uganda kwa kilo.`));
  utterance.lang=state.lang==='sw'?'sw-KE':'en-GB';speechSynthesis.cancel();speechSynthesis.speak(utterance);
}
function compareDialog(){
  const rows=state.prices.rows,dates=new Set(rows.map(r=>r.last_month)),types=new Set(rows.map(r=>r.price_status));
  showModal(`<h2>${text('Compare market references','Linganisha bei za kumbukumbu')}</h2><p>${text('Same crop · UGX per kilogram · wholesale-level references.','Zao lilelile · shilingi za Uganda kwa kilo · bei za kiwango cha jumla.')}</p>${dates.size>1?`<p class="notice">${text('These records come from different months. They are not a same-day comparison.','Taarifa hizi ni za miezi tofauti. Si ulinganisho wa siku moja.')}</p>`:''}${types.size>1?`<p class="form-note">${text('This list mixes observed wholesale prices and wholesale estimates.','Orodha inachanganya bei halisi za jumla na makadirio ya bei za jumla.')}</p>`:''}<div class="table-wrap"><table class="training-table"><thead><tr><th>${text('Market','Soko')}</th><th>${text('Recorded','Mwezi')}</th><th>UGX/kg</th><th>${text('Basis','Aina')}</th></tr></thead><tbody>${rows.map(r=>`<tr><td><button data-compare-market="${esc(r.market)}">${esc(r.market)}</button></td><td>${r.last_month}${r.stale?' · '+text('old','zamani'):''}</td><td>${money(r.market_price)}</td><td>${r.price_status==='observed wholesale'?text('Observed','Iliyorekodiwa'):text('Estimated','Makadirio')}${r.market_factor_basis==='assumed'?' · '+text('assumed conversion','ubadilishaji wa dhana'):''}</td></tr>`).join('')}</tbody></table></div><p>${text('Transport costs are not included. A higher market price does not automatically mean more money to take home.','Gharama za usafiri hazijajumuishwa. Bei kubwa ya soko haimaanishi moja kwa moja mapato makubwa zaidi.')}</p>`);
}
function renderStaff(){
  const markets=[...new Set(state.catalog.crops.flatMap(c=>c.markets))].sort();
  $('#app').innerHTML=`<button class="back" data-back="welcome">← Farmer start screen</button><h1>Kiosk staff</h1><p>Settings apply only to this device. This public setup view contains no credentials or farmer records.</p><form id="setup-form" class="setup-form"><label for="kiosk-name">Kiosk name</label><input id="kiosk-name" maxlength="60" value="${esc(setup.name)}" required><label for="default-market">Default market</label><select id="default-market"><option value="">Latest available core-area market</option>${markets.map(m=>`<option ${m===setup.market?'selected':''}>${esc(m)}</option>`).join('')}</select><p class="form-note">If the chosen market has no record for a crop, the market step uses an available market and shows its date.</p><label for="default-language">Starting language</label><select id="default-language"><option value="en" ${setup.language==='en'?'selected':''}>English</option><option value="sw" ${setup.language==='sw'?'selected':''}>Kiswahili</option></select><label for="idle-minutes">Reset after inactivity</label><select id="idle-minutes">${[2,3,5].map(n=>`<option value="${n}" ${Number(setup.idleMinutes)===n?'selected':''}>${n} minutes</option>`).join('')}</select><button class="primary" type="submit">Save device setup</button><p id="setup-status" role="status"></p></form><h2>Service status</h2><p>Published source data through <strong>${esc(state.catalog.data_end)}</strong>. ${offlineRecord?'Using cached records.':'Records were retrieved from the local backend.'}</p><p>Live SMS: <strong>not connected</strong>. Quality-grade mapping: <strong>not validated</strong>.</p><div class="detail-actions"><button id="sms-open">SMS simulator (test only)</button><button id="training-open">Training and data details</button></div><p class="form-note">Device speech, local language wording and offline reload need acceptance checks on each kiosk tablet. No Acholi support is claimed.</p>`;
  $('#setup-form').onsubmit=e=>{e.preventDefault();setup={name:$('#kiosk-name').value.trim()||DEFAULTS.name,market:$('#default-market').value,language:$('#default-language').value,idleMinutes:Number($('#idle-minutes').value)};try{localStorage.setItem('fairprice:setup',JSON.stringify(setup));$('#setup-status').textContent='Device setup saved.';}catch{$('#setup-status').textContent='Settings apply for this session; device storage is unavailable.';}};
  $('#sms-open').onclick=()=>smsDialog();$('#training-open').onclick=trainingDialog;
}
async function trainingDialog(){
  const version=navigationVersion;
  try{const data=await api('/api/training'),m=data.metrics;if(version!==navigationVersion)return;showModal(`<h2>Training and data details</h2><p>Source data through ${m.data_end}. Team model trained ${esc(m.trained_at)}.</p><p>The API serves precomputed monthly forecasts. It does not generate a current price on request.</p><table class="training-table"><thead><tr><th>Crop</th><th>Model MAPE</th><th>Last-price baseline</th></tr></thead><tbody>${Object.entries(m.by_crop).map(([c,r])=>`<tr><td>${esc(state.catalog.crops.find(x=>x.id===c)?.name||c)}</td><td>${r.model.mape_pct}%</td><td>${r.naive.mape_pct}%</td></tr>`).join('')}</tbody></table><ul>${data.limitations.map(s=>`<li>${esc(s)}</li>`).join('')}</ul><p>These are development scores, not guaranteed accuracy. Historical forecasts are deliberately outside the farmer price screen.</p>`);}catch{if(version===navigationVersion)showModal('<h2>Training details unavailable</h2><p>Reconnect and try again.</p>');}
}
// Staff-only simulator. No phone number, SMS dispatch or farmer registration.
function smsDialog(){
  const selected=state.crop||state.catalog.crops[0].id;
  showModal(`<h2>SMS simulator · test only</h2><div class="sms-layout"><div class="sms-form"><label for="sms-crop">Crop</label><select id="sms-crop">${state.catalog.crops.map(c=>`<option value="${c.id}" ${c.id===selected?'selected':''}>${esc(c.name)}</option>`).join('')}</select><label for="sms-market">Market</label><select id="sms-market"></select><label for="sms-grade">Pricing scenario</label><select id="sms-grade"><option>A</option><option selected>B</option><option>C</option></select><p>No message is sent. Provider submission and handset delivery have not been tested.</p></div><div class="phone"><small>SMS · FAIRPRICE</small><p id="sms-message" class="sms-message">Loading…</p></div></div>`);
  let version=0;
  const update=async()=>{const target=$('#sms-message'),v=++version;try{const response=await fetch('/api/sms/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({crop:$('#sms-crop').value,market:$('#sms-market').value,grade:$('#sms-grade').value,language:state.lang})});if(!response.ok)throw Error();const data=await response.json();if(v===version)target.textContent=data.message;}catch{if(v===version)target.textContent='Simulator unavailable. Reconnect to the backend.';}};
  const markets=()=>{const crop=state.catalog.crops.find(c=>c.id===$('#sms-crop').value);$('#sms-market').innerHTML=crop.markets.map(m=>`<option ${m===state.market?'selected':''}>${esc(m)}</option>`).join('');update();};
  $('#sms-crop').onchange=markets;$('#sms-market').onchange=update;$('#sms-grade').onchange=update;markets();
}
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.lang){state.lang=b.dataset.lang;go('categories');}
  if(b.dataset.back)go(b.dataset.back);
  if(b.dataset.category){state.category=b.dataset.category;go('list');}
  if(b.dataset.crop)openCrop(b.dataset.crop);
  if(b.dataset.compareMarket){state.market=b.dataset.compareMarket;closeModal();go('detail');}
});
$('.brand').onclick=e=>{e.preventDefault();resetSession();};$('#start-over').onclick=resetSession;
$('#language').onclick=()=>{state.lang=state.lang==='en'?'sw':'en';closeModal();render();};
$('#staff-open').onclick=()=>{closeModal();go('staff');};$('.close').onclick=closeModal;
(async()=>{try{state.catalog=await api('/api/crops');render();}catch{$('#app').innerHTML='<h1>Crop data unavailable</h1><p>Reconnect to load crop prices. No saved records are available on this device.</p>';}})();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>setConnection('Offline page caching is unavailable. Keep the kiosk connected.'));
