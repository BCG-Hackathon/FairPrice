const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {lang:'en',screen:'welcome',category:null,crop:null,market:null,catalog:null,prices:null};
const text = (en,sw) => state.lang === 'sw' ? sw : en;
const cropName = c => state.lang === 'sw' ? c.name_sw : c.name;
const money = p => new Intl.NumberFormat('en-UG').format(p);
async function api(path) {
  try {
    const response = await fetch(path);
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    try {localStorage.setItem('fairprice:'+path,JSON.stringify({data,saved:new Date().toISOString()}));}catch{}
    $('#connection').textContent=''; return data;
  } catch(error) {
    let saved; try {saved=JSON.parse(localStorage.getItem('fairprice:'+path));}catch{}
    if(saved){$('#connection').textContent=`Saved data · cached ${new Date(saved.saved).toLocaleString()}. Observation dates below still apply.`;return saved.data;}
    throw error;
  }
}
const image = c => `<img src="${esc(c.image)}" alt="${esc(cropName(c))} illustration">`;
function render(){
  document.documentElement.lang=state.lang;
  $('#language').textContent=text('English / Kiswahili','Kiswahili / English');
  const app=$('#app');
  if(state.screen==='welcome') {
    app.innerHTML=`<div class="intro"><div class="plant" aria-hidden="true">🌱</div><h1>${text('Know your crop’s value.','Fahamu thamani ya mazao yako.')}</h1><p class="muted">${text('Compare published market prices before you sell. No account or phone required at the kiosk.','Linganisha bei za soko zilizochapishwa kabla ya kuuza. Huhitaji akaunti au simu kwenye kioski.')}</p><h2>${text('Choose your language','Chagua lugha')}</h2><div class="big-actions"><button class="primary" data-lang="en">English</button><button data-lang="sw">Kiswahili</button></div><p class="form-note">${text('Monthly WFP data · Northern Uganda · Six supported crops','Takwimu za kila mwezi za WFP · Uganda Kaskazini · Mazao sita')}</p></div>`;
  } else if(state.screen==='categories') {
    app.innerHTML=`<button class="back" data-back="welcome">← ${text('Language','Lugha')}</button><div class="intro"><h1>${text('What do you grow?','Unalima nini?')}</h1><p class="muted">${text('Choose a category to check market prices.','Chagua aina ya mazao kuona bei za soko.')}</p></div><div class="big-actions"><button class="category" data-category="grains"><img src="/assets/maize.svg" alt="">${text('Grains & beans','Nafaka na maharagwe')}</button><button class="category" data-category="vegetables"><img src="/assets/cassava_fresh.svg" alt="">${text('Vegetables & roots','Mboga na mizizi')}</button></div><p class="muted" style="text-align:center">${text('Only crops available in our dataset are shown.','Tunaonyesha mazao yaliyopo kwenye takwimu zetu pekee.')}</p>`;
  } else if(state.screen==='list') {
    app.innerHTML=`<button class="back" data-back="categories">← ${text('Categories','Aina za mazao')}</button><div class="list-head"><div><h1>${state.category==='grains'?text('Grains & beans','Nafaka na maharagwe'):text('Vegetables & roots','Mboga na mizizi')}</h1><p class="muted">${text('Choose your crop','Chagua zao lako')}</p></div><input id="search" type="search" placeholder="${text('Search crops…','Tafuta mazao…')}" aria-label="${text('Search crops','Tafuta mazao')}"></div><div class="crop-list" id="crop-list"></div>`;
    renderList(''); $('#search').addEventListener('input',e=>renderList(e.target.value));
  } else if(state.screen==='detail') renderDetail();
}
function renderList(query){
  const crops=state.catalog.crops.filter(c=>c.category===state.category && `${c.name} ${c.name_sw}`.toLowerCase().includes(query.toLowerCase()));
  $('#crop-list').innerHTML=crops.map(c=>`<button class="crop-row" data-crop="${esc(c.id)}">${image(c)}<span><strong>${esc(cropName(c))}</strong><small>${esc(c.form)}</small></span><span class="arrow" aria-hidden="true">›</span></button>`).join('')||`<p class="empty">${text('No matching crop.','Hakuna zao linalolingana.')}</p>`;
}
function renderDetail(){
  const crop=state.catalog.crops.find(c=>c.id===state.crop);
  const row=state.prices.rows.find(r=>r.market===state.market)||state.prices.rows[0];state.market=row.market;
  $('#app').innerHTML=`<button class="back" data-back="list">← ${text('Crops','Mazao')}</button><div class="detail-top">${image(crop)}<div><h1>${esc(cropName(crop))}</h1><p class="muted">${esc(crop.form)} · UGX/kg</p></div></div><div class="market-picker"><label for="market">${text('Market','Soko')}</label><select id="market">${state.prices.rows.map(r=>`<option ${r.market===row.market?'selected':''} value="${esc(r.market)}">${esc(r.market)} · ${r.last_month}</option>`).join('')}</select><button id="refresh">${text('Refresh','Sasisha')}</button></div>
  <div class="source-strip"><strong>${text('Recorded','Ilirekodiwa')}: ${row.last_month}</strong> · ${esc(row.market)}<br>${text('Published observation','Bei iliyochapishwa')}: UGX ${money(row.observed_price)}/kg (${esc(row.observed_price_type)})<br>${text('Base market estimate','Makadirio ya bei ya soko')}: <strong>UGX ${money(row.market_price)}/kg</strong> · ${esc(row.market_factor_basis)} factor × ${row.market_factor}<br><a href="https://data.humdata.org/dataset/wfp-food-prices-for-uganda" target="_blank" rel="noreferrer">WFP / HDX source</a> · ${text('Data through','Takwimu hadi')} ${state.prices.data_end}</div>
  <div class="notice">${text('These are dated monthly reference prices, not today’s buyer offers.','Hizi ni bei za kumbukumbu za kila mwezi, si ofa za wanunuzi za leo.')} ${row.stale?text('This market record is over six months old.','Taarifa hii ya soko ina zaidi ya miezi sita.'):''} ${row.market_factor_basis==='assumed'?text('Wholesale conversion for this crop is assumed, not directly measured.','Ubadilishaji wa bei ya jumla kwa zao hili ni dhana, haujapimwa moja kwa moja.'):''}</div>
  <div class="grades">${['A','B','C'].map((g,i)=>`<section class="grade"><h2>${text('Grade','Daraja')} ${g}</h2>${image(crop)}<div class="price">${money(row.grade_prices[g])}</div><div class="unit">UGX / kg</div><p>${[text('+4% above base market estimate','+4% juu ya makadirio ya msingi'),text('Base market estimate','Makadirio ya msingi ya soko'),text('−5.5% below base market estimate','−5.5% chini ya makadirio ya msingi')][i]}</p><button data-sms-grade="${g}">${text('Preview SMS','Hakiki SMS')}</button></section>`).join('')}</div>
  <p class="form-note">${text('A/B/C are our indicative pricing scenarios. These percentages are not verified UNBS rules. Images identify crops; they do not certify a grade or food safety.','A/B/C ni makadirio yetu ya bei. Asilimia hizi si kanuni za UNBS zilizothibitishwa. Picha hutambulisha mazao, si ubora au usalama wa chakula.')}</p><div class="detail-actions"><button class="primary" id="read-aloud">${text('Read this price aloud','Soma bei kwa sauti')}</button></div>
  <details class="forecast"><summary>${text('See the model forecast and its date','Ona utabiri wa modeli na tarehe yake')}</summary><p>${text('Forecast for','Utabiri wa')} <strong>${row.forecast_month}</strong>: UGX ${money(row.market_price_forecast)}/kg (${esc(row.forecast_method)}). ${row.forecast_is_past?text('This forecast month has already passed. It is a historical model output, not a current prediction.','Mwezi huu umepita. Huu ni utabiri wa zamani, si wa sasa.'):''}<br>${text('Source retail-to-wholesale factor also applies to this forecast.','Kigezo cha bei ya rejareja hadi jumla kinatumika pia kwa utabiri huu.')}</p></details>`;
  $('#market').addEventListener('change',e=>{state.market=e.target.value;renderDetail();});
  $('#refresh').onclick=()=>openCrop(state.crop,state.market);
  $('#read-aloud').onclick=()=>{
    if(!('speechSynthesis' in window)){showModal('<h2>Read aloud unavailable</h2><p>This browser does not provide speech. Ask the kiosk attendant to read the displayed price.</p>');return;}
    const phrase=text(`${crop.name} at ${row.market}. Recorded ${row.last_month}. Base market estimate ${row.grade_prices.B} Ugandan shillings per kilogram. Not a current buyer offer.`,`${crop.name_sw}, ${row.market}. Mwezi ${row.last_month}. Makadirio ya bei ${row.grade_prices.B} shilingi za Uganda kwa kilo.`);
    const voice=new SpeechSynthesisUtterance(phrase);voice.lang=state.lang==='sw'?'sw-KE':'en-GB';speechSynthesis.cancel();speechSynthesis.speak(voice);
  };
}
async function openCrop(id,market=null){
  try{state.prices=await api('/api/prices/'+encodeURIComponent(id));state.crop=id;state.market=market;state.screen='detail';render();}catch{showModal('<h2>Prices unavailable</h2><p>Reconnect and try again. No saved price is available for this crop.</p>');}
}
function showModal(html){$('#modal-content').innerHTML=html;$('#modal').showModal();}
function smsDialog(grade='B'){
  const selected=state.crop||state.catalog.crops[0].id;
  showModal(`<h2>${text('SMS preview','Hakiki SMS')}</h2><p class="muted">${text('See the same price on a basic phone. No registration needed.','Ona bei hiyo hiyo kwenye simu ya kawaida. Huhitaji kujisajili.')}</p><div class="sms-layout"><div class="sms-form"><label for="sms-crop">Crop</label><select id="sms-crop">${state.catalog.crops.map(c=>`<option value="${c.id}" ${c.id===selected?'selected':''}>${esc(cropName(c))}</option>`).join('')}</select><label for="sms-market">Market</label><select id="sms-market"></select><label for="sms-grade">Grade</label><select id="sms-grade">${['A','B','C'].map(g=>`<option ${g===grade?'selected':''}>${g}</option>`).join('')}</select><p class="form-note">Preview only. No message is sent. Live SMS requires a provisioned provider.</p></div><div class="phone"><small>SMS · FAIRPRICE</small><p class="sms-message" id="sms-message">Loading…</p></div></div>`);
  let previewVersion=0;
  function updateMarkets(){const c=state.catalog.crops.find(c=>c.id===$('#sms-crop').value);$('#sms-market').innerHTML=c.markets.map(m=>`<option ${m===state.market?'selected':''}>${esc(m)}</option>`).join('');updatePreview();}
  async function updatePreview(){
    const target=$('#sms-message'),version=++previewVersion;try{const result=await fetch('/api/sms/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({crop:$('#sms-crop').value,market:$('#sms-market').value,grade:$('#sms-grade').value,language:state.lang})});if(!result.ok)throw Error();const reply=await result.json();if(version===previewVersion)target.textContent=reply.message;}catch{if(version===previewVersion)target.textContent='SMS preview unavailable offline. The kiosk price remains visible.';}
  }
  $('#sms-crop').onchange=updateMarkets;$('#sms-market').onchange=updatePreview;$('#sms-grade').onchange=updatePreview;updateMarkets();
}
document.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.dataset.lang){state.lang=button.dataset.lang;state.screen='categories';render();}
  if(button.dataset.back){state.screen=button.dataset.back;render();}
  if(button.dataset.category){state.category=button.dataset.category;state.screen='list';render();}
  if(button.dataset.crop)openCrop(button.dataset.crop);
  if(button.dataset.smsGrade)smsDialog(button.dataset.smsGrade);
});
$('.brand').onclick=e=>{e.preventDefault();state.screen='welcome';state.crop=null;render();};
$('#language').onclick=()=>{state.lang=state.lang==='en'?'sw':'en';render();};
$('.close').onclick=()=>{$('#modal').close();if('speechSynthesis' in window)speechSynthesis.cancel();};
$('#sms-open').onclick=()=>state.catalog&&smsDialog();
$('#training-open').onclick=async()=>{
  try{const d=await api('/api/training'),m=d.metrics;showModal(`<h2>What is behind the price?</h2><p>LightGBM learns next-month log price changes from monthly WFP records, lagged changes, seasonal patterns and market/crop categories. The API serves saved outputs; it does not invent prices.</p><p>Team training: ${esc(m.trained_at)}<br>Data through ${m.data_end} · ${m.all_rows} labelled month-pairs<br>Holdout forecast origins from ${m.test_from}: ${m.overall.rows} predictions</p><table class="training-table"><thead><tr><th>Crop</th><th>Model MAPE</th><th>Last-price baseline</th></tr></thead><tbody>${Object.entries(m.by_crop).map(([k,v])=>`<tr><td>${esc(state.catalog.crops.find(c=>c.id===k)?.name||k)}</td><td>${v.model.mape_pct}%</td><td>${v.naive.mape_pct}%</td></tr>`).join('')}</tbody></table><p class="form-note">Lower MAPE is better. These are the team's saved development scores, not guaranteed accuracy.</p><ul>${d.limitations.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`);}catch{showModal('<h2>Training details unavailable</h2><p>Reconnect and try again.</p>');}
};
(async()=>{try{state.catalog=await api('/api/crops');render();}catch{$('#app').innerHTML='<h1>Cannot load crop data</h1><p>Start the backend and reload this page. No prices have been cached yet.</p>';}})();
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{
  $('#connection').textContent='Offline page caching is unavailable in this browser. Keep the kiosk connected.';
});
