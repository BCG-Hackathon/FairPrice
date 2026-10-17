const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
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
  $('#start-over').textContent=text('Home','Nyumbani');
  $('#staff-open').textContent=text('Kiosk staff','Wahudumu wa kioski');
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
    <section class="grade-details" aria-label="${text('Produce grades','Madaraja ya mazao')}"><div class="grades">${['A','B','C'].map((g,i)=>`<section class="grade"><h2>${text('Grade','Daraja')} ${g}</h2><div class="grade-photo" role="img" aria-label="${esc(GRADE_CAPTIONS[crop.id][i][state.lang==='sw'?1:0])}" style="background-image:url('/assets/grades/${crop.id}.png');background-position:${i*50}% center"></div><ul class="grade-points">${GRADE_POINTS[crop.id][i][state.lang==='sw'?1:0].map(point=>`<li>${esc(point)}</li>`).join('')}</ul><span class="grade-price-label">${text('Price','Bei')}</span><div class="price"><span class="grade-currency">UGX </span>${money(row.grade_prices[g])}<span class="grade-per-kg">/kg</span></div></section>`).join('')}</div></section>
    <p class="price-context">${esc(row.market)} · ${month(row.last_month)} · ${row.stale?text('Older reference price','Bei ya zamani ya kumbukumbu'):text('Indicative price','Bei ya makadirio')}</p>
    <button class="back screen-back" data-back="list">← ${text('Crops','Mazao')}</button>`;
}
function renderStaff(){
  const markets=[...new Set(state.catalog.crops.flatMap(c=>c.markets))].sort(),lang=l=>state.lang===l?'selected':'';
  $('#app').innerHTML=`<button class="back" data-back="welcome">← ${text('Farmer start screen','Skrini ya mwanzo ya mkulima')}</button><h1>${text('Kiosk staff','Wahudumu wa kioski')}</h1><section class="sms-updates"><h2>${text('Fair Value Updates','Taarifa za Fair Value')}</h2><p>${text('Text farmers the latest prices per kg (UGX, grades A, B and C). Prices published through','Tuma wakulima bei za karibuni kwa kilo (UGX, madaraja A, B na C). Bei zilizochapishwa hadi')} <strong>${esc(state.catalog.data_end)}</strong>.</p><div id="staff-key-row" class="setup-form" hidden><label for="staff-key">${text('Staff access key','Ufunguo wa wahudumu')}</label><input id="staff-key" type="password" autocomplete="off"></div><fieldset class="sms-recipients"><legend>${text('Recipients','Wapokeaji')}</legend><label class="sms-all"><input type="checkbox" id="sms-all"> <strong>${text('Everyone (bulk)','Wote (kwa pamoja)')}</strong> <span id="sms-count"></span></label><ul id="sms-contacts"><li class="form-note">${text('Loading recipients…','Inapakia wapokeaji…')}</li></ul><form id="sms-add" class="sms-add"><input id="sms-name" maxlength="60" placeholder="${text('Name','Jina')}" aria-label="${text('Recipient name','Jina la mpokeaji')}" required><input id="sms-phone" type="tel" maxlength="24" placeholder="${text('Phone number','Nambari ya simu')}" aria-label="${text('Recipient phone number','Nambari ya simu ya mpokeaji')}" required><label><input type="checkbox" id="sms-add-consent" required> ${text('Agreed to receive SMS','Amekubali kupokea SMS')}</label><button type="submit">${text('Add','Ongeza')}</button></form><p id="sms-add-status" class="form-note" role="status"></p></fieldset><div class="sms-send"><label for="sms-language">${text('Language','Lugha')}</label><select id="sms-language"><option value="en" ${lang('en')}>English</option><option value="sw" ${lang('sw')}>Kiswahili</option></select><button id="send-updates" class="primary" disabled>${text('Send Updates','Tuma Taarifa')}</button></div><div id="sms-results" role="status"></div></section><details class="device-setup"><summary>${text('Device setup','Mipangilio ya kifaa')}</summary><form id="setup-form" class="setup-form"><label for="kiosk-name">${text('Kiosk name','Jina la kioski')}</label><input id="kiosk-name" maxlength="60" value="${esc(setup.name)}" required><label for="default-market">${text('Default market','Soko la msingi')}</label><select id="default-market"><option value="">${text('Latest available core-area market','Soko la karibuni linalopatikana')}</option>${markets.map(m=>`<option ${m===setup.market?'selected':''}>${esc(m)}</option>`).join('')}</select><label for="default-language">${text('Starting language','Lugha ya kuanzia')}</label><select id="default-language"><option value="en" ${setup.language==='en'?'selected':''}>English</option><option value="sw" ${setup.language==='sw'?'selected':''}>Kiswahili</option></select><label for="idle-minutes">${text('Reset after inactivity','Anza upya baada ya kutotumika')}</label><select id="idle-minutes">${[2,3,5].map(n=>`<option value="${n}" ${Number(setup.idleMinutes)===n?'selected':''}>${text(`${n} minutes`,`Dakika ${n}`)}</option>`).join('')}</select><button class="primary" type="submit">${text('Save device setup','Hifadhi mipangilio')}</button><p id="setup-status" role="status"></p></form></details>`;
  $('#setup-form').onsubmit=e=>{e.preventDefault();setup={name:$('#kiosk-name').value.trim()||DEFAULTS.name,market:$('#default-market').value,language:$('#default-language').value,idleMinutes:Number($('#idle-minutes').value)};try{localStorage.setItem('fairprice:setup',JSON.stringify(setup));$('#setup-status').textContent=text('Device setup saved.','Mipangilio imehifadhiwa.');}catch{$('#setup-status').textContent=text('Settings apply for this session; device storage is unavailable.','Mipangilio inatumika kwa kipindi hiki tu; hifadhi ya kifaa haipatikani.');}};
  $('#send-updates').onclick=()=>farmerUpdates(false);
  $('#sms-all').onchange=e=>{$$('[data-contact-phone]').forEach(box=>{box.checked=e.target.checked;});smsSelection();};
  $('#sms-contacts').onchange=smsSelection;
  $('#sms-contacts').onclick=async e=>{const id=e.target.closest('[data-remove-contact]')?.dataset.removeContact;if(!id)return;e.target.disabled=true;try{await staffRequest(`/api/sms/contacts/${id}`,null,'DELETE');loadContacts();}catch(error){$('#sms-add-status').textContent=error.message;e.target.disabled=false;}};
  $('#sms-add').onsubmit=async e=>{e.preventDefault();const status=$('#sms-add-status');
    try{const c=await staffRequest('/api/sms/contacts',{name:$('#sms-name').value,phone:$('#sms-phone').value,consent:$('#sms-add-consent').checked});e.target.reset();status.textContent=text(`Added ${c.name} (${c.phone}).`,`Ameongezwa: ${c.name} (${c.phone}).`);loadContacts(c.phone);}catch(error){status.textContent=error.message;}};
  $('#staff-key').onchange=()=>loadContacts();
  // On the kiosk machine itself the server provides the staff key; elsewhere staff type it.
  fetch('/api/sms/staff-key',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{const input=$('#staff-key');if(d?.key&&input&&!input.value)input.value=d.key;}).catch(()=>{}).finally(()=>{if($('#staff-key-row'))$('#staff-key-row').hidden=!!$('#staff-key').value;loadContacts();});
}
let smsContacts=[];
async function loadContacts(added){
  const list=$('#sms-contacts');if(!list)return;
  const kept=new Set($$('[data-contact-phone]').filter(box=>box.checked).map(box=>box.dataset.contactPhone)),first=!$$('[data-contact-phone]').length;
  try{const data=await staffRequest('/api/sms/contacts');if(!list.isConnected)return;smsContacts=data.contacts;
    $('#sms-phone').placeholder=`${text('Phone','Simu')} (0… = ${data.country_code})`;
    list.innerHTML=smsContacts.length?smsContacts.map(c=>`<li><label><input type="checkbox" data-contact-phone="${esc(c.phone)}" ${first||kept.has(c.phone)||c.phone===added?'checked':''}> <span>${esc(c.name)}</span> <small>${esc(c.phone)}</small></label><button type="button" data-remove-contact="${c.id}" aria-label="${text('Remove','Ondoa')} ${esc(c.name)}">${text('Remove','Ondoa')}</button></li>`).join(''):`<li class="form-note">${text('No recipients yet. Add one below.','Bado hakuna wapokeaji. Ongeza hapa chini.')}</li>`;
  }catch(error){if(list.isConnected)list.innerHTML=`<li class="form-note">${esc(error.message)}</li>`;}
  smsSelection();
}
function smsSelection(){
  const boxes=$$('[data-contact-phone]'),chosen=boxes.filter(box=>box.checked).length,button=$('#send-updates');if(!button)return;
  $('#sms-all').checked=boxes.length>0&&chosen===boxes.length;$('#sms-all').indeterminate=chosen>0&&chosen<boxes.length;
  $('#sms-count').textContent=boxes.length?text(`· ${chosen} of ${boxes.length} selected`,`· ${chosen} kati ya ${boxes.length} wamechaguliwa`):'';
  button.disabled=!chosen;button.textContent=chosen?text(`Send Updates to ${chosen} recipient${chosen>1?'s':''}`,`Tuma Taarifa kwa wapokeaji ${chosen}`):text('Send Updates','Tuma Taarifa');
}
function smsParts(characters){return characters<=160?1:Math.ceil(characters/153);}
const SMS_STATUS={sent:['sent','imetumwa'],skipped:['skipped','imerukwa'],failed:['failed','imeshindikana']};
// Staff-only: preview the farmer price SMS for the ticked recipients, then send on confirmation.
async function farmerUpdates(send){
  const target=$('#sms-results'),version=navigationVersion,button=$('#send-updates');
  const phones=$$('[data-contact-phone]').filter(box=>box.checked).map(box=>box.dataset.contactPhone);
  if(!phones.length){target.textContent=text('Tick at least one recipient.','Chagua angalau mpokeaji mmoja.');return;}
  const names=Object.fromEntries(smsContacts.map(c=>[c.phone,c.name]));
  button.disabled=true;target.textContent=send?text('Sending updates…','Inatuma taarifa…'):text('Preparing the message…','Inaandaa ujumbe…');
  try{const data=await staffRequest('/api/sms/farmers',{phones,language:$('#sms-language').value,dry_run:!send,consent_confirmed:send});if(version!==navigationVersion)return;
    if(!send){
      const to=esc(phones.map(p=>names[p]||p).join(', ')),parts=smsParts(data.characters);
      target.innerHTML=`<h3>${text('Check the message','Kagua ujumbe')}</h3><div class="phone"><small>SMS · FAIR VALUE</small><p class="sms-message">${esc(data.text)}</p></div><p>${text(`${data.characters} characters · ${parts} SMS parts each · to ${to}`,`Herufi ${data.characters} · sehemu ${parts} za SMS kwa kila mmoja · kwa ${to}`)}</p><div class="detail-actions"><button id="sms-confirm" class="primary">${text(`Confirm and send to ${phones.length}`,`Thibitisha na utume kwa ${phones.length}`)}</button><button id="sms-cancel">${text('Cancel','Ghairi')}</button></div>`;
      $('#sms-confirm').onclick=()=>farmerUpdates(true);$('#sms-cancel').onclick=()=>{target.textContent=text('Not sent.','Haikutumwa.');};
      $('#sms-confirm').focus();
    }else{
      const sent=data.deliveries.filter(d=>d.status==='sent').length;
      target.innerHTML=`<h3>${sent?text(`Sent to ${sent} of ${phones.length} recipient${phones.length>1?'s':''}`,`Imetumwa kwa ${sent} kati ya ${phones.length}`):text('Nothing was sent','Hakuna kilichotumwa')}</h3><ul>${data.deliveries.map(d=>`<li>${esc(names[d.to]||'')} ${esc(d.to)}: <strong>${esc(SMS_STATUS[d.status]?text(...SMS_STATUS[d.status]):d.status)}</strong>${d.error?` · ${esc(d.error)}`:''}</li>`).join('')}</ul>`;
    }
  }catch(error){if(version===navigationVersion)target.textContent=error.message;}
  finally{if(button.isConnected)smsSelection();}
}
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.lang){state.lang=b.dataset.lang;go('categories');}
  if(b.dataset.back)go(b.dataset.back);
  if(b.dataset.category){state.category=b.dataset.category;go('list');}
  if(b.dataset.crop)openCrop(b.dataset.crop);
});
$('.brand').onclick=e=>{e.preventDefault();resetSession();};$('#start-over').onclick=resetSession;
$('#language').onclick=()=>{state.lang=state.lang==='en'?'sw':'en';closeModal();render();};
$('#staff-open').onclick=()=>{closeModal();go('staff');};$('.close').onclick=closeModal;
(async()=>{try{state.catalog=await api('/api/crops');render();}catch{$('#app').innerHTML='<h1>Crop data unavailable</h1><p>Reconnect to load crop prices. No saved records are available on this device.</p>';}})();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>setConnection('Offline page caching is unavailable. Keep the kiosk connected.'));

async function staffRequest(path,body,method){
  const key=$('#staff-key')?.value||'';if(!key){if($('#staff-key-row'))$('#staff-key-row').hidden=false;throw Error(text('Enter the staff access key. It is never saved.','Weka ufunguo wa wahudumu. Hauhifadhiwi.'));}
  const response=await fetch(path,{method:method||(body?'POST':'GET'),cache:'no-store',headers:{'X-Admin-Token':key,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(!response.ok){
    const detail=response.status===422?(await response.json().catch(()=>({}))).detail:null,badPhone=typeof detail==='string'&&detail.match(/^'(.*)' is not a valid phone number$/);
    throw Error(response.status===401?text('Staff access denied. Check the server access key.','Ufunguo wa wahudumu umekataliwa. Angalia ufunguo wa seva.'):badPhone?text(detail,`'${badPhone[1]}' si nambari sahihi ya simu`):typeof detail==='string'?detail:text('Request failed. Reconnect and try again.','Ombi limeshindikana. Unganisha tena ujaribu.'));
  }
  return response.status===204?null:response.json();
}
