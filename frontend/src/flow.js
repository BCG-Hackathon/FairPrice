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
const GRADE_CAPTIONS={
  beans:[['Intact, sorted beans','Maharagwe yaliyopangwa, yasiyovunjika'],['Some broken or shrivelled beans','Baadhi yamevunjika au kunyauka'],['More broken or shrivelled beans','Mengi zaidi yamevunjika au kunyauka']],
  maize:[['Clean, intact grain','Nafaka safi zisizovunjika'],['Some broken, uneven kernels','Baadhi ya punje zimevunjika'],['More broken or shrivelled kernels','Punje nyingi zaidi zimevunjika au kusinyaa']],
  sorghum:[['Clean, uniform grain','Nafaka safi zinazofanana'],['Some uneven or broken grain','Baadhi hazifanani au zimevunjika'],['More broken or shrivelled grain','Nyingi zaidi zimevunjika au kusinyaa']],
  millet:[['Clean, uniform grain','Nafaka safi zinazofanana'],['Some uneven grain and pieces','Baadhi hazifanani au zimevunjika'],['More broken or shrivelled grain','Nyingi zaidi zimevunjika au kusinyaa']],
  cassava_fresh:[['Fresh-looking, intact roots','Mizizi inayoonekana mibichi, haijaharibika'],['Minor skin marks; drier cut ends','Alama ndogo kwenye ngozi; ncha kavu zaidi'],['More shrivelling and dry cut ends','Mizizi iliyosinyaa na ncha kavu zaidi']],
  leafy_vegetables:[['Crisp, green leaves','Majani mabichi ya kijani'],['Some wilting and yellow edges','Baadhi yamenyauka na kuwa ya njano pembeni'],['More wilting and yellowing','Kunyauka na rangi ya njano zaidi']]
};
// Illustrative visual cues, not certified grading thresholds.
const GRADE_POINTS={
  "beans": [
    [
      [
        "Whole, unbroken beans",
        "Similar size and colour",
        "Few shrivelled beans"
      ],
      [
        "Maharagwe mazima, hayajavunjika",
        "Ukubwa na rangi zinazofanana",
        "Machache yamesinyaa"
      ]
    ],
    [
      [
        "Some split or broken beans",
        "Sizes are less even",
        "Some beans are shrivelled"
      ],
      [
        "Baadhi yamepasuka au kuvunjika",
        "Ukubwa hautoshi kufanana",
        "Baadhi ya maharagwe yamesinyaa"
      ]
    ],
    [
      [
        "Many split or broken beans",
        "More small, shrivelled beans",
        "Large differences in size"
      ],
      [
        "Mengi yamepasuka au kuvunjika",
        "Mengi zaidi ni madogo na yamesinyaa",
        "Tofauti kubwa za ukubwa"
      ]
    ]
  ],
  "maize": [
    [
      [
        "Whole, intact kernels",
        "Similar kernel size",
        "Few broken pieces"
      ],
      [
        "Punje nzima, hazijavunjika",
        "Ukubwa wa punje unafanana",
        "Vipande vichache vilivyovunjika"
      ]
    ],
    [
      [
        "Some broken kernels",
        "Uneven kernel sizes",
        "Some shrivelled kernels"
      ],
      [
        "Baadhi ya punje zimevunjika",
        "Ukubwa wa punje haufanani",
        "Baadhi ya punje zimesinyaa"
      ]
    ],
    [
      [
        "Many broken kernels",
        "More small, shrivelled kernels",
        "Many loose kernel pieces"
      ],
      [
        "Punje nyingi zimevunjika",
        "Punje nyingi zaidi ni ndogo na zimesinyaa",
        "Vipande vingi vya punje"
      ]
    ]
  ],
  "sorghum": [
    [
      [
        "Mostly whole grains",
        "Similar grain size",
        "Few shrivelled grains"
      ],
      [
        "Nafaka nyingi ni nzima",
        "Ukubwa wa nafaka unafanana",
        "Nafaka chache zimesinyaa"
      ]
    ],
    [
      [
        "Some broken grains",
        "Uneven grain sizes",
        "Some shrivelled grains"
      ],
      [
        "Baadhi ya nafaka zimevunjika",
        "Ukubwa wa nafaka haufanani",
        "Baadhi ya nafaka zimesinyaa"
      ]
    ],
    [
      [
        "Many broken grains",
        "More shrivelled grains",
        "More small grain fragments"
      ],
      [
        "Nafaka nyingi zimevunjika",
        "Nafaka nyingi zaidi zimesinyaa",
        "Vipande vidogo vingi vya nafaka"
      ]
    ]
  ],
  "millet": [
    [
      [
        "Mostly whole grains",
        "Similar size and colour",
        "Few broken pieces"
      ],
      [
        "Nafaka nyingi ni nzima",
        "Ukubwa na rangi zinazofanana",
        "Vipande vichache vilivyovunjika"
      ]
    ],
    [
      [
        "Some broken grains",
        "Less even grain sizes",
        "Some shrivelled grains"
      ],
      [
        "Baadhi ya nafaka zimevunjika",
        "Ukubwa wa nafaka haufanani sana",
        "Baadhi ya nafaka zimesinyaa"
      ]
    ],
    [
      [
        "Many broken grains",
        "More small, shrivelled grains",
        "Many loose grain pieces"
      ],
      [
        "Nafaka nyingi zimevunjika",
        "Nafaka nyingi zaidi ni ndogo na zimesinyaa",
        "Vipande vingi vya nafaka"
      ]
    ]
  ],
  "cassava_fresh": [
    [
      [
        "Whole roots with little damage",
        "Skin looks smooth and firm",
        "Cut ends look fresh"
      ],
      [
        "Mizizi mizima yenye uharibifu mdogo",
        "Ngozi inaonekana laini na imara",
        "Ncha zilizokatwa zinaonekana mbichi"
      ]
    ],
    [
      [
        "Small scratches on the skin",
        "Cut ends look slightly dry",
        "Some roots look less firm"
      ],
      [
        "Michubuko midogo kwenye ngozi",
        "Ncha zilizokatwa zinaonekana kavu kidogo",
        "Baadhi ya mizizi haionekani imara sana"
      ]
    ],
    [
      [
        "More wrinkling on the skin",
        "Cut ends look dry",
        "More roots look shrivelled"
      ],
      [
        "Mikunjo mingi zaidi kwenye ngozi",
        "Ncha zilizokatwa zinaonekana kavu",
        "Mizizi mingi zaidi inaonekana imesinyaa"
      ]
    ]
  ],
  "leafy_vegetables": [
    [
      [
        "Leaves look crisp and upright",
        "Mostly green leaves",
        "Little visible wilting"
      ],
      [
        "Majani yanaonekana imara na yamesimama",
        "Majani mengi ni ya kijani",
        "Kunyauka kidogo kunakoonekana"
      ]
    ],
    [
      [
        "Some leaves are drooping",
        "Some yellow leaf edges",
        "Leaves look less crisp"
      ],
      [
        "Baadhi ya majani yamelegea",
        "Kingo za baadhi ya majani ni za njano",
        "Majani hayaonekani imara sana"
      ]
    ],
    [
      [
        "Many leaves are wilted",
        "More yellow leaves and edges",
        "Leaves look limp and curled"
      ],
      [
        "Majani mengi yamenyauka",
        "Majani na kingo nyingi zaidi ni za njano",
        "Majani yanaonekana yamelegea na kujikunja"
      ]
    ]
  ]
};
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
function go(screen){navigationVersion++;state.screen=screen;render();focusScreen();window.scrollTo?.(0,0);}
function focusScreen(){const title=$('#app h1');if(title){title.tabIndex=-1;title.focus({preventScroll:true});}}
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
  $('#buyer-register').textContent=text('Register as buyer','Jisajili kama mnunuzi');
  $('#footer-copy').textContent=text('Farmers: no account needed · Dated reference prices','Wakulima: hamhitaji akaunti · Bei za kumbukumbu');
  $('#app').dataset.screen=state.screen;
  if(!state.catalog)return;
  if(state.screen==='welcome'){
    $('#app').innerHTML=`<h1 class="sr-only">${text('Choose your language','Chagua lugha')}</h1><div class="language-choices"><button class="image-choice" data-lang="en"><img src="/assets/design/english.png" alt="United Kingdom flag"><span>ENGLISH</span></button><button class="image-choice" data-lang="sw"><img src="/assets/design/swahili.png" alt="Uganda flag"><span>SWAHILI</span></button></div><p class="welcome-note">${text('Check a market price before you sell. No account or phone needed.','Angalia bei ya soko kabla ya kuuza. Huhitaji akaunti au simu.')}<br><small>${esc(setup.name)}</small></p>`;
  }else if(state.screen==='categories'){
    $('#app').innerHTML=`<h1 class="page-title">${text('SELECT A CATEGORY BELOW','CHAGUA KILASIO CHINI')}</h1><div class="category-choices"><button class="category image-choice" data-category="grains"><img src="/assets/beans.png" alt="">${text('GRAINS & BEANS','NAFAKA NA MAHARAGWE')}</button><button class="category image-choice" data-category="vegetables"><img src="/assets/leafy_vegetables.png" alt="">${text('VEGETABLES & ROOTS','MBOGA NA MIZIZI')}</button></div><button class="back screen-back" data-back="welcome">← ${text('Language','Lugha')}</button>`;
  }else if(state.screen==='list'){
    $('#app').innerHTML=`<div class="list-head"><h1 class="page-title">${state.category==='grains'?text('AVAILABLE GRAINS & BEANS','NAFAKA NA MAHARAGWE YALIYOPO'):text('AVAILABLE VEGETABLES & ROOTS','MBOGA NA MIZIZI ILIYOPO')}</h1><div class="search-field"><label class="sr-only" for="search">${text('Search crops','Tafuta mazao')}</label><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="13" cy="13" r="9"/><path d="m20 20 9 9"/></svg><input id="search" type="search" aria-label="${text('Search crops','Tafuta mazao')}" placeholder="${text('Search crops…','Tafuta mazao…')}"></div></div><div id="crop-list" class="crop-list"></div><button class="back screen-back" data-back="categories">← ${text('Categories','Aina za mazao')}</button>`;renderList('');$('#search').oninput=e=>renderList(e.target.value);
  }else if(state.screen==='detail')renderDetail();
  else if(state.screen==='staff')renderStaff();
}
function renderList(query){const list=state.catalog.crops.filter(c=>c.category===state.category&&`${c.name} ${c.name_sw}`.toLowerCase().includes(query.toLowerCase()));$('#crop-list').innerHTML=list.map(c=>`<button class="crop-row" data-crop="${c.id}"><span><strong>${esc(cropName(c))}</strong><small>${esc(c.form)}</small></span></button>`).join('')||`<p class="empty">${text('No matching crop with available data.','Hakuna zao lenye taarifa linalolingana.')}</p>`;}

async function openCrop(id,market=null){
  const version=++navigationVersion;
  try{const data=await api('/api/prices/'+encodeURIComponent(id));if(version!==navigationVersion)return;if(!data.rows?.length)throw Error();
    state.prices=data;state.crop=id;state.market=[market,setup.market].find(m=>data.rows.some(r=>r.market===m))||data.rows[0].market;state.screen='detail';render();focusScreen();window.scrollTo?.(0,0);
  }catch{if(version===navigationVersion)showModal(`<h2>${text('Price unavailable','Bei haipatikani')}</h2><p>${text('No published or saved price is available for this crop. Reconnect and try again, or choose another crop.','Hakuna bei iliyochapishwa au kuhifadhiwa kwa zao hili. Unganisha tena au chagua zao jingine.')}</p>`);}
}
function current(){return state.prices?.rows.find(r=>r.market===state.market);}
function renderDetail(){
  const crop=state.catalog.crops.find(c=>c.id===state.crop),row=current();if(!row){go('list');return;}
  $('#app').innerHTML=`<div class="detail-top"><h1>${esc(cropName(crop))}</h1></div>
    <section class="grade-details" aria-label="${text('Produce grades','Madaraja ya mazao')}"><div class="grades">${['A','B','C'].map((g,i)=>`<section class="grade"><h2>${text('Grade','Daraja')} ${g}</h2><div class="grade-photo" role="img" aria-label="${esc(GRADE_CAPTIONS[crop.id][i][state.lang==='sw'?1:0])}" style="background-image:url('/assets/grades/${crop.id}.png');background-position:${i*50}% center"></div><ul class="grade-points">${GRADE_POINTS[crop.id][i][state.lang==='sw'?1:0].map(point=>`<li>${esc(point)}</li>`).join('')}</ul><span class="grade-price-label">${text('Price','Bei')}</span><div class="price"><span class="grade-currency">UGX </span>${money(row.grade_prices[g])}<span class="grade-per-kg">/kg</span></div><button class="primary" data-buyers-grade="${g}">${text('Get buyers','Pata wanunuzi')}</button></section>`).join('')}</div></section>
    <p class="price-context">${esc(row.market)} · ${month(row.last_month)} · ${row.stale?text('Older reference price','Bei ya zamani ya kumbukumbu'):text('Indicative price','Bei ya makadirio')}</p>
    <button class="back screen-back" data-back="list">← ${text('Crops','Mazao')}</button>`;
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
  $('#app').innerHTML=`<button class="back" data-back="welcome">← Farmer start screen</button><h1>Kiosk staff</h1><p>Settings apply only to this device. This public setup view contains no credentials or farmer records.</p><form id="setup-form" class="setup-form"><label for="kiosk-name">Kiosk name</label><input id="kiosk-name" maxlength="60" value="${esc(setup.name)}" required><label for="default-market">Default market</label><select id="default-market"><option value="">Latest available core-area market</option>${markets.map(m=>`<option ${m===setup.market?'selected':''}>${esc(m)}</option>`).join('')}</select><p class="form-note">Farmers go straight from a crop to its grade prices. If the configured market has no record, an available market is used; its name and date appear below the cards.</p><label for="default-language">Starting language</label><select id="default-language"><option value="en" ${setup.language==='en'?'selected':''}>English</option><option value="sw" ${setup.language==='sw'?'selected':''}>Kiswahili</option></select><label for="idle-minutes">Reset after inactivity</label><select id="idle-minutes">${[2,3,5].map(n=>`<option value="${n}" ${Number(setup.idleMinutes)===n?'selected':''}>${n} minutes</option>`).join('')}</select><button class="primary" type="submit">Save device setup</button><p id="setup-status" role="status"></p></form><h2>Service status</h2><p>Published source data through <strong>${esc(state.catalog.data_end)}</strong>. ${offlineRecord?'Using cached records.':'Records were retrieved from the local backend.'}</p><p>Live SMS: <strong>farmer price updates via BulkSMS</strong> (see below). Quality-grade mapping: <strong>not validated</strong>.</p><div class="detail-actions"><button id="sms-open">SMS simulator (test only)</button><button id="training-open">Training and data details</button></div><p class="form-note">Device speech, local language wording and offline reload need acceptance checks on each kiosk tablet. No Acholi support is claimed.</p>`;
  $('#setup-form').onsubmit=e=>{e.preventDefault();setup={name:$('#kiosk-name').value.trim()||DEFAULTS.name,market:$('#default-market').value,language:$('#default-language').value,idleMinutes:Number($('#idle-minutes').value)};try{localStorage.setItem('fairprice:setup',JSON.stringify(setup));$('#setup-status').textContent='Device setup saved.';}catch{$('#setup-status').textContent='Settings apply for this session; device storage is unavailable.';}};
  $('#sms-open').onclick=()=>smsDialog();$('#training-open').onclick=trainingDialog;
  if(state.prices&&current()){
    const crop=state.catalog.crops.find(c=>c.id===state.crop),row=current();
    const reference=document.createElement('section');
    reference.innerHTML=`<h2>Selected crop reference</h2><p>${esc(crop.name)} · ${esc(row.market)} · ${month(row.last_month)}${row.stale?' · Over six months old':''}</p><p>Market reference: UGX ${money(row.market_price)}/kg. Published observation: UGX ${money(row.observed_price)}/kg (${esc(row.observed_price_type)}). Wholesale conversion: × ${row.market_factor} (${esc(row.market_factor_basis)}).</p><p>A +4%, B base and C −5.5% are application assumptions, not certified grades or buyer offers. Grade photos are illustrative; agree actual quality with the buyer.</p><div class="detail-actions"><button id="read-aloud">Read aloud</button><button id="compare-open">Compare markets</button><button id="refresh">Check for an updated record</button></div>`;
    $('#app').append(reference);
    $('#read-aloud').onclick=()=>readPrice(crop,row);$('#compare-open').onclick=compareDialog;$('#refresh').onclick=()=>openCrop(state.crop,state.market);
  }
  const tools=document.createElement('section');tools.innerHTML='<h2>Buyer review & source automation</h2><p>Registrations stay private until reviewed. Review is not proof of identity or ability to pay. Listings expire after 30 days.</p><label for="staff-key">Staff access key</label><input id="staff-key" type="password" autocomplete="off"><p class="form-note">Never saved on this device. Closing this staff session clears it. Configure ADMIN_TOKEN on the server; the default token is rejected.</p><div class="detail-actions"><button id="review-buyers">Review buyer registrations</button><button id="source-check">Check official source now</button><button id="source-status">Automation status</button></div><div id="staff-results" role="status"></div>';$('#app').append(tools);
  $('#review-buyers').onclick=reviewBuyers;$('#source-check').onclick=()=>sourceStatus(true);$('#source-status').onclick=()=>sourceStatus(false);
  const updates=document.createElement('section');updates.innerHTML=`<h2>Farmer SMS updates</h2><p>Texts farmers the latest vegetable, fruit and grain/crop prices per kg (UGX, grades A, B and C) from the published records. Uses the staff access key above. You see the exact message before anything is sent.</p><div class="setup-form"><label for="sms-phones">Farmer phone numbers</label><input id="sms-phones" autocomplete="off" placeholder="+256700000000, +256711111111"><p class="form-note">Include the country code. Separate numbers with commas.</p><label for="sms-group">Or a BulkSMS phonebook group</label><input id="sms-group" maxlength="100" autocomplete="off"><label for="sms-language">Message language</label><select id="sms-language"><option value="en" ${state.lang==='en'?'selected':''}>English</option><option value="sw" ${state.lang==='sw'?'selected':''}>Kiswahili</option></select></div><div class="detail-actions"><button id="send-updates" class="primary">Send Updates</button></div><div id="sms-results" role="status"></div>`;$('#app').append(updates);
  $('#send-updates').onclick=()=>farmerUpdates(false);
}
function smsParts(characters){return characters<=160?1:Math.ceil(characters/153);}
// Staff-only: preview the farmer price SMS, then send it after consent is confirmed.
async function farmerUpdates(send){
  const target=$('#sms-results'),version=navigationVersion,button=$('#send-updates');
  const phones=[...new Set($('#sms-phones').value.split(/[\s,;]+/).filter(Boolean))],group=$('#sms-group').value.trim()||null;
  if(!phones.length&&!group){target.textContent='Enter farmer phone numbers or a BulkSMS group.';return;}
  const invalid=phones.filter(p=>!/^\+[1-9][0-9]{7,14}$/.test(p));
  if(invalid.length){target.textContent=`Check these numbers (use the country code, e.g. +256…): ${invalid.join(', ')}`;return;}
  const recipients=[phones.length?`${phones.length} number${phones.length>1?'s':''}`:'',group?`group "${group}"`:''].filter(Boolean).join(' and ');
  button.disabled=true;target.textContent=send?'Sending updates…':'Preparing the message…';
  try{const data=await staffRequest('/api/sms/farmers',{phones,group,language:$('#sms-language').value,dry_run:!send,consent_confirmed:send});if(version!==navigationVersion)return;
    if(!send){
      target.innerHTML=`<h3>Check the message</h3><div class="phone"><small>SMS · FAIRPRICE</small><p class="sms-message">${esc(data.text)}</p></div><p>${data.characters} characters · ${smsParts(data.characters)} SMS parts per farmer · to ${esc(recipients)}</p><label><input type="checkbox" id="sms-consent"> These farmers agreed to receive FairPrice SMS</label><div class="detail-actions"><button id="sms-confirm" class="primary" disabled>Confirm and send</button><button id="sms-cancel">Cancel</button></div>`;
      $('#sms-consent').onchange=e=>{$('#sms-confirm').disabled=!e.target.checked;};
      $('#sms-confirm').onclick=()=>farmerUpdates(true);$('#sms-cancel').onclick=()=>{target.textContent='Not sent.';};
    }else{
      const sent=data.deliveries.filter(d=>d.status==='sent').length;
      target.innerHTML=`<h3>${sent?`Sent to ${sent} recipient${sent>1?'s':''}`:'Nothing was sent'}</h3><ul>${data.deliveries.map(d=>`<li>${esc(d.to)}: <strong>${esc(d.status)}</strong>${d.error?` · ${esc(d.error)}`:''}</li>`).join('')}</ul>`;
    }
  }catch(error){if(version===navigationVersion)target.textContent=error.message;}
  finally{if(button.isConnected)button.disabled=false;}
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
  if(b.dataset.buyersGrade)buyerDirectory(b.dataset.buyersGrade);
  if(b.dataset.compareMarket){state.market=b.dataset.compareMarket;closeModal();go('detail');}
});
$('.brand').onclick=e=>{e.preventDefault();resetSession();};$('#start-over').onclick=resetSession;
$('#language').onclick=()=>{state.lang=state.lang==='en'?'sw':'en';closeModal();render();};
$('#staff-open').onclick=()=>{closeModal();go('staff');};$('.close').onclick=closeModal;
$('#buyer-register').onclick=()=>registerBuyer();
(async()=>{try{state.catalog=await api('/api/crops');render();}catch{$('#app').innerHTML='<h1>Crop data unavailable</h1><p>Reconnect to load crop prices. No saved records are available on this device.</p>';}})();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>setConnection('Offline page caching is unavailable. Keep the kiosk connected.'));

async function buyerDirectory(grade){
  const version=navigationVersion,crop=state.crop;
  showModal(`<h2>${text('Potential buyers','Wanunuzi')} · ${grade}</h2><p id="buyer-list">${text('Loading…','Inapakia…')}</p>`);
  try{const response=await fetch(`/api/buyers?crop=${encodeURIComponent(crop)}&grade=${grade}`,{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();if(version!==navigationVersion||!$('#buyer-list'))return;
    $('#buyer-list').outerHTML=`<div class="buyer-list">${data.buyers.length?data.buyers.map(b=>`<article class="buyer-card"><h3>${esc(b.name)}</h3><p>${esc(b.location)} · ${text('Wants grade','Anataka daraja')} ${esc(b.grade)}</p>${b.phone?`<a href="tel:${esc(b.phone)}">${esc(b.phone)}</a>`:`<p>${text('Ask kiosk staff to arrange contact.','Muombe mhudumu wa kioski akusaidie kuwasiliana.')}</p>`}<p class="form-note">${text('Listing expires','Orodha inaisha')}: ${esc(b.expires_at.slice(0,10))}</p></article>`).join(''):`<p>${text('No active buyer is registered for this crop and grade yet.','Bado hakuna mnunuzi aliyesajiliwa kwa zao na daraja hili.')}</p>`}</div><p>${text('No prices are listed. Agree quality, quantity, collection and price directly. Kiosk review does not guarantee identity, payment or a sale.','Hakuna bei zilizoonyeshwa. Kubalianeni kuhusu ubora, kiasi, ukusanyaji na bei. Ukaguzi wa kioski hauhakikishi utambulisho, malipo au mauzo.')}</p><button id="register-this-buyer">${text('I want to buy this crop','Nataka kununua zao hili')}</button>`;
    $('#register-this-buyer').onclick=()=>registerBuyer(grade);
  }catch{if(version===navigationVersion&&$('#buyer-list'))$('#buyer-list').textContent=text('Connect to see active buyers. Buyer contact details are not cached on this shared device.','Unganisha kuona wanunuzi. Mawasiliano yao hayahifadhiwi kwenye kifaa hiki cha pamoja.');}
}
function registerBuyer(grade='B'){
  const crop=state.crop||state.catalog.crops[0].id;
  showModal(`<h2>${text('Register as a buyer','Jisajili kama mnunuzi')}</h2><p>${text('Tell farmers what you want to buy. No price is listed. Staff review your request before it appears.','Waambie wakulima unataka kununua nini. Hakuna bei inayoonyeshwa. Mhudumu atakagua ombi kabla ya kuchapishwa.')}</p><form id="buyer-form" class="setup-form"><label for="buyer-name">${text('Buyer / business name','Jina la mnunuzi / biashara')}</label><input id="buyer-name" minlength="2" maxlength="80" required><label for="buyer-location">${text('Location / collection area','Eneo la biashara / ukusanyaji')}</label><input id="buyer-location" minlength="2" maxlength="100" required><label for="buyer-crop">${text('Crop wanted','Zao unalotaka')}</label><select id="buyer-crop">${state.catalog.crops.map(c=>`<option value="${c.id}" ${c.id===crop?'selected':''}>${esc(cropName(c))}</option>`).join('')}</select><label for="buyer-grade">${text('Grade wanted—confirm actual quality with the farmer','Daraja unalotaka—kubaliana kuhusu ubora halisi')}</label><select id="buyer-grade">${['A','B','C'].map(g=>`<option ${g===grade?'selected':''}>${g}</option>`).join('')}</select><label class="check-label"><input type="checkbox" id="buyer-publish-phone"> ${text('Show my phone number to farmers (optional)','Onyesha nambari yangu kwa wakulima (hiari)')}</label><label for="buyer-phone">${text('Phone number, with country code','Nambari ya simu, pamoja na msimbo wa nchi')}</label><input id="buyer-phone" type="tel" placeholder="+256…" maxlength="16" disabled><p class="form-note">${text('Without a public phone number, farmers will ask kiosk staff to arrange contact.','Bila nambari ya umma, wakulima watamuomba mhudumu awasaidie kuwasiliana.')}</p><label class="check-label"><input type="checkbox" id="buyer-consent" required> ${text('I agree to publish my name, location and crop/grade request after review. The listing expires after 30 days.','Nakubali kuchapisha jina, eneo na zao/daraja ninalotaka baada ya ukaguzi. Orodha inaisha baada ya siku 30.')}</label><button class="primary" type="submit">${text('Submit for kiosk review','Wasilisha kwa ukaguzi wa kioski')}</button><p id="buyer-submit-status" role="status"></p></form>`);
  $('#buyer-publish-phone').onchange=e=>{const input=$('#buyer-phone');input.disabled=!e.target.checked;input.required=e.target.checked;if(!e.target.checked)input.value='';};
  $('#buyer-form').onsubmit=async e=>{e.preventDefault();const version=navigationVersion,form=e.target,button=form.querySelector('button[type=submit]'),target=$('#buyer-submit-status');button.disabled=true;
    const body={name:$('#buyer-name').value,location:$('#buyer-location').value,crop:$('#buyer-crop').value,grade:$('#buyer-grade').value,consent_to_listing:$('#buyer-consent').checked,publish_phone:$('#buyer-publish-phone').checked,phone:$('#buyer-publish-phone').checked?$('#buyer-phone').value.trim():null};
    try{const response=await fetch('/api/buyers/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok){if(response.status===429)throw Error('limit');throw Error('invalid');}if(version!==navigationVersion||!target.isConnected)return;form.reset();showModal(`<h2>${text('Registration received','Usajili umepokelewa')}</h2><p>${text('Your request is waiting for kiosk review. It is not public yet. Ask kiosk staff to approve, update or withdraw it.','Ombi lako linasubiri ukaguzi wa kioski. Bado halijachapishwa. Muombe mhudumu aliidhinishe, alisasishe au aliondoe.')}</p>`);}catch(error){if(target.isConnected){target.textContent=error.message==='limit'?text('Registration limit reached. Ask kiosk staff.','Kikomo cha usajili kimefikiwa. Muulize mhudumu.'):text('Could not submit. Check your details and connection. Your request has not been confirmed.','Imeshindikana kuwasilisha. Angalia taarifa na muunganisho. Ombi halijathibitishwa.');button.disabled=false;}}
  };
}
async function staffRequest(path,body){
  const key=$('#staff-key')?.value||'';if(!key)throw Error('Enter the staff access key. It is never saved.');
  const response=await fetch(path,{method:body?'POST':'GET',cache:'no-store',headers:{'X-Admin-Token':key,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(!response.ok)throw Error(response.status===401?'Staff access denied. Check the server access key.':'Request failed. Reconnect and try again.');return response.json();
}
async function reviewBuyers(){
  const target=$('#staff-results'),version=navigationVersion;target.textContent='Loading registrations…';
  try{const data=await staffRequest('/api/buyers/manage');if(version!==navigationVersion)return;target.innerHTML=data.buyers.length?data.buyers.map(b=>`<article class="buyer-card"><h3>${esc(b.name)} · ${esc(b.status)}</h3><p>${esc(b.location)} · ${esc(b.crop)} · ${esc(b.grade)}${b.phone?' · '+esc(b.phone):' · Contact through kiosk'}</p>${(b.status==='pending'?['approve','reject']:['withdraw']).map(action=>`<button data-review-id="${b.id}" data-review-action="${action}">${action}</button>`).join('')}</article>`).join(''):'No pending or active registrations.';
    target.querySelectorAll('[data-review-id]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await staffRequest(`/api/buyers/${button.dataset.reviewId}/review`,{action:button.dataset.reviewAction});if(version===navigationVersion)reviewBuyers();}catch(error){if(version===navigationVersion){target.textContent=error.message;}}});
  }catch(error){if(version===navigationVersion)target.textContent=error.message;}
}
async function sourceStatus(run){
  const target=$('#staff-results'),version=navigationVersion;target.textContent=run?'Checking official source and validating prices…':'Loading source status…';
  try{const data=run?await staffRequest('/api/source/refresh',{}):await(await fetch('/api/source/status',{cache:'no-store'})).json();if(version!==navigationVersion)return;
    const latest=run?data:data.latest;target.innerHTML=`<h3>Source automation</h3><p>${run?'Check completed.':`Scheduled checks: ${data.enabled?'enabled':'disabled'}.`}</p>${latest?`<p>Status: <strong>${esc(latest.status)}</strong><br>Checked: ${esc(latest.checked_at||'')}<br>Latest published month: ${esc(latest.latest_month||'unchanged')}<br>${esc(latest.error||'')}</p><p>${latest.auditor?`Tiny auditor: ${latest.auditor.trees} IsolationForest trees, ${latest.auditor.training_changes} training changes.`:''}</p>`:'<p>No source check has run yet.</p>'}<p>New prices must pass source, schema, unit, date, coverage and anomaly checks. A check cannot invent newer observations or retrain the forecast model.</p>`;
    if(run&&data.status==='published'){state.catalog=await api('/api/crops');}
  }catch(error){if(version===navigationVersion)target.textContent=error.message||'Source status unavailable.';}
}
