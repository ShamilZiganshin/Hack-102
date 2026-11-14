'use strict';

const $=s=>document.querySelector(s),hash=new URLSearchParams(location.hash.slice(1));let access=hash.get('key')||sessionStorage.getItem('pumpAccess')||'';
if(access)sessionStorage.setItem('pumpAccess',access);if(hash.has('key'))history.replaceState(null,'',location.pathname+location.search);

let tag='',stream=null,busy=false,auto=false,selectedResult=null,original=false,telemetryBusy=false;

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function status(s,error=false){$('#status').textContent=s;$('#status').classList.toggle('error',error)}

async function api(path,options={}){const r=await fetch(path,{...options,headers:{'X-Access-Key':access,...options.headers}});if(r.status===401){location.assign('/login');throw Error('Войдите в кабинет')}if(!r.ok){let b=await r.json().catch(()=>({error:r.statusText}));throw Error(b.error||'Ошибка сервера')}return r}
async function json(path,options){return (await api(path,options)).json()}

$('#accessSave').onclick=()=>{access=$('#accessCode').value.trim();sessionStorage.setItem('pumpAccess',access);init()};
async function init(){try{const rows=await json('/api/equipment');$('#access').hidden=true;$('#equipment').innerHTML='<option value="">Выбрать из БД…</option>'+rows.map(x=>`<option value="${esc(x.tag)}">${esc(x.tag)} · № ${esc(x.serial_no)}</option>`).join('');if(tag)$('#equipment').value=tag;trends();const q=new URLSearchParams(location.search).get('asset');if(q&&rows.some(r=>r.tag===q))await choose(q);status(tag?'Паспорт '+tag+' открыт. Можно осматривать оборудование.':'Сервер подключён. Сфотографируйте QR на насосе.')}catch(e){status(e.message,true)}}

async function choose(value){stagedCapture=null;$('#saveCapture').hidden=true;showAlerts(null);endLive();tag=value;$('#equipment').value=tag;trends();$('#result').hidden=true;if(!tag)return;try{const p=await json('/api/passport?tag='+encodeURIComponent(tag));if(p.tag!==tag)return;$('#assetTitle').textContent=p.tag;$('#identity').textContent='Заводской № '+p.serial_no+' · '+(p.location||'Местоположение не задано');$('#modelName').textContent=[p.model_code,p.manufacturer].filter(Boolean).join(' / ')||'Модель не указана';const fmt=x=>x.text??(x.value!==null?x.value:(x.min===null?'до '+x.max:x.max===null?'от '+x.min:x.min+' … '+x.max));const row=x=>`<div class="spec"><span>${esc(x.label)}</span><b>${esc(fmt(x))} ${esc(x.unit)}</b><small>${esc(x.condition||'Паспортное значение')} · документ № ${esc(x.document_id)}, стр. ${esc(x.page)}</small></div>`;$('#specs').innerHTML=p.passport_parameters.filter(x=>/power|flow|pressure|fluid_temperature|mass|speed/.test(x.code)).slice(0,8).map(row).join('');$('#allSpecs').innerHTML=p.passport_parameters.map(row).join('');$('#documents').replaceChildren();for(const d of p.documents){const b=document.createElement('button');b.className='doc';b.textContent=(d.id===p.passport_document_id?'Скачать паспорт (PDF) · ':'Скачать · ')+d.filename;b.onclick=async()=>{try{const blob=await(await api('/api/document/'+d.id)).blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=d.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){status(e.message,true)}};$('#documents').append(b)}$('#approved').innerHTML=p.limits.length?p.limits.map(l=>`<p>${esc(l.metric)}: ${esc(l.lower_bound??'—')} … ${esc(l.upper_bound??'—')} ${esc(l.unit)}<br>${esc(l.filename||'Источник')}: ${esc(l.source_locator)} · утверждено ${esc(l.approved_by)}</p>`).join(''):'<p class="notice">В БД нет утверждённых уставок для этого насоса. Значения по ГОСТ не подставляются автоматически. Паспортные диапазоны выше — характеристики и условия применения, а не универсальные пороги датчиков.</p>';$('#limitsNotice').textContent=p.limits.length?'Сравнение только с утверждёнными уставками из БД; источник указан в паспорте.':'Утверждённых уставок нет. Состояние «норма по ГОСТ» определить нельзя.';$('#maintenance').innerHTML=p.maintenance.length?p.maintenance.map(m=>`<p>${esc(m.code)}: до ТО ${esc(m.hours_remaining??'нет данных')} ч</p>`).join(''):'<p>Утверждённый интервал ТО и текущая наработка не заданы. Ресурс 11 000 ч не считается интервалом ТО.</p>';$('#passport').hidden=$('#sensors').hidden=false;await updateTelemetry();await historyList();status('Насос '+tag+' найден. Можно осматривать оборудование.')}catch(e){status(e.message,true)}}

$('#equipment').onchange=e=>choose(e.target.value);

const states={no_data:'Нет данных',no_limit:'Нет утверждённой уставки',within:'В пределах утверждённой уставки',outside:'Выход за утверждённую уставку',stale:'Устаревшие данные (> 30 с)'};

async function updateTelemetry(){if(!tag||telemetryBusy)return;telemetryBusy=true;const requested=tag;try{const r=await json('/api/telemetry?tag='+encodeURIComponent(tag)+'&demo='+($('#demo').checked?'1':'0'));if(requested!==tag)return;showAlerts(r);$('#telemetrySource').textContent=r.source+(r.demo?' · '+r.scenario:'');$('#limitsNotice').textContent=r.demo?'Сценарий симулятора. Пороги загружены из БД со статусом demo; это не ГОСТ и не утверждённые нормы.':'Сравнение с утверждёнными уставками. Если их нет, состояние нормы неизвестно.';$('#dataBadge').textContent=r.demo?'ДЕМО / симулятор':r.measured_at?'Данные из БД':'Нет измерений';$('#metrics').innerHTML=r.metrics.map(m=>`<div class="metric ${m.state}"><div class="label">${esc(m.label)}</div><div class="value">${m.value===null?'—':esc(Number(m.value).toLocaleString('ru-RU',{maximumFractionDigits:2}))} <span class="unit">${esc(m.unit)}</span></div><div class="state">${r.demo?'Симуляция · ':''}${esc(r.demo?states[m.state].replace(/утверждённ/g,'демонстрационн'):states[m.state])}${m.limit?'<br>Уставка: '+esc(m.limit.lower_bound??'—')+' … '+esc(m.limit.upper_bound??'—'):''}</div></div>`).join('');$('#sensorTimes').textContent='Измерение: '+(r.measured_at?new Date(r.measured_at).toLocaleTimeString():'нет')+' · ответ сервера '+new Date(r.server_at).toLocaleTimeString()}catch(e){showAlerts(null);$('#telemetrySource').textContent='Связь с датчиками потеряна: '+e.message;$('#dataBadge').textContent='Нет связи';$('#metrics').querySelectorAll('.state').forEach(x=>x.textContent='Нет связи — значения не актуальны')}finally{telemetryBusy=false}}

$('#demo').onchange=updateTelemetry;setInterval(updateTelemetry,2000);

async function health(){try{const h=await(await fetch('/api/health')).json();const models=h.models||h.gpu?.models||{};const ready=['rust','oil','crack'].every(k=>models[k]===true||models[k]?.ready);$('#serverLamp').textContent=ready?'● модели готовы':'● модели загружаются';$('#serverLamp').style.color=ready?'#a2e8c5':'#f6d18b'}catch(e){$('#serverLamp').textContent='● нет сервера';$('#serverLamp').style.color='#ffa48f'}}health();setInterval(health,5000);

$('#cameraStart').onclick=async()=>{if(stream){stopCamera();return}if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){status('Для непрерывной камеры откройте доверенный HTTPS из файла «Подключить телефон.html». Сейчас доступны кнопки съёмки отдельных фото.',true);return}try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false});$('#video').srcObject=stream;await $('#video').play();$('#cameraPlaceholder').hidden=true;$('#liveBadge').hidden=false;$('#cameraStart').textContent='Выключить камеру';$('#cameraMode').textContent='Live';status('Камера готова. Наведите на QR и нажмите «Сфотографировать QR».')}catch(e){stopCamera();status(e.name==='NotAllowedError'?'Браузер не разрешил доступ к камере. Разрешите камеру в настройках сайта и нажмите «Включить камеру» ещё раз. Или выберите насос из списка и нажмите «Выбрать фото из галереи».':'Камера недоступна: '+e.message+'. Выберите фото из галереи.',true)}};

function stopCamera(){endLive();$('#auto').textContent='Непрерывный осмотр';stream?.getTracks().forEach(t=>t.stop());stream=null;$('#video').srcObject=null;$('#cameraPlaceholder').hidden=false;$('#liveBadge').hidden=true;$('#cameraStart').textContent='Включить камеру';$('#cameraMode').textContent='Снимки'}

async function frame(maxSize=1280){const v=$('#video');if(!v.videoWidth)throw Error('Камера ещё не готова');const c=document.createElement('canvas'),scale=Math.min(1,maxSize/Math.max(v.videoWidth,v.videoHeight));c.width=Math.round(v.videoWidth*scale);c.height=Math.round(v.videoHeight*scale);c.getContext('2d').drawImage(v,0,0,c.width,c.height);return new Promise(r=>c.toBlob(r,'image/jpeg',.9))}

$('#scanQr').onclick=async()=>{if(busy)return;if(stream){try{await scan(await frame())}catch(e){status(e.message,true)}}else $('#qrFile').click()};$('#qrFile').onchange=async e=>{if(e.target.files[0])await scan(e.target.files[0]);e.target.value=''};

async function scan(blob){busy=true;$('#auto').disabled=true;status('Распознаём QR на сервере…');try{const r=await json('/api/qr',{method:'POST',body:blob});await choose(r.tag);status('Выбран '+r.tag+'. Нажмите «Непрерывный осмотр».')}catch(e){status(e.message,true)}finally{busy=false;$('#auto').disabled=false}}

$('#shot').onclick=async()=>{if(busy)return;if(!tag){status('Сначала выберите насос по QR.',true);return}if(stream){try{await inspect(await frame())}catch(e){status(e.message,true)}}else $('#equipmentFile').click()};$('#equipmentFile').onchange=async e=>{if(e.target.files[0])await inspect(e.target.files[0]);e.target.value=''};

const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function bodyLabel(state){
 return ({intact:'Конструкция в порядке · внешний осмотр',broken:'Повреждение конструкции · корпус привода'})[state]||'Ракурс не распознан';
}
for(const [current,other] of [['bodyMode','gaugeMode'],['gaugeMode','bodyMode']]){
 $('#'+current).onchange=()=>{if($('#'+current).checked)$('#'+other).checked=false;showFrameFindings(null);$('#gpuOverlay').hidden=true;};
}
let stagedCapture=null;
async function persistCapture(){
 const shot=stagedCapture;if(!shot||tag!==shot.tag)return;
 const button=$('#saveCapture');button.disabled=true;
 try{
  await json('/api/field/capture?tag='+encodeURIComponent(shot.tag),{method:'POST',headers:{'X-Field-Request':'1'},body:shot.blob});
  if(stagedCapture===shot){stagedCapture=null;button.hidden=true}
  status('Фото сохранено в истории осмотров');return true;
 }catch(e){status(e.message,true)}finally{button.disabled=false}
}
$('#saveCapture').onclick=persistCapture;
async function inspect(blob){if(busy)return;
 stagedCapture={blob,tag};$('#saveCapture').hidden=false;busy=true;
 const saved=await persistCapture();busy=false;if(!saved)return;
 if($('#bodyMode').checked){
  busy=true;const requestTag=tag;
  try{
   const packet=await json('/api/ar-frame?mode=body',{method:'POST',body:blob});
   const img=new Image();img.src='data:image/jpeg;base64,'+packet.image;await img.decode();
   if(tag!==requestTag||!$('#bodyMode').checked)return;
   const c=$('#gpuOverlay');c.width=img.width;c.height=img.height;c.getContext('2d').drawImage(img,0,0);c.hidden=false;
   $('#cameraPlaceholder').hidden=true;showFrameFindings(null,bodyLabel(packet.structure));status(bodyLabel(packet.structure));
  }catch(e){status(e.message,true)}finally{busy=false}
  return;
 }
busy=true;const captured=new Date().toISOString(),requestTag=tag;$('#shot').disabled=true;status('Отправляем кадр: ржавчина, масло и трещины. Вычисления на компьютере…');try{const {id}=await json('/api/analyze?tag='+encodeURIComponent(tag)+'&quality='+($('#quality').checked?'1':'0')+'&cracks=1',{method:'POST',body:blob,headers:{'X-Captured-At':captured}});let r,started=Date.now();do{await sleep(700);r=await json('/api/jobs/'+id);status((r.stage==='crack_yolo'?'Ржавчина и масло готовы. Трещины: YOLO · '+(r.crack_progress?.status||'запуск')+' · ':'Сервер обрабатывает зафиксированный кадр · ')+((Date.now()-started)/1000).toFixed(0)+' с');if(Date.now()-started>1500000)throw Error('Обработка превысила 25 минут. Проверьте сервер.')}while(!['done','error'].includes(r.status));if(r.status==='error')throw Error(r.error);if(requestTag===tag){await renderResult(r);await historyList();status('Готово за '+r.seconds+' с. Осмотр сохранён в БД.'+(auto?' Следующий кадр снимается после обработки.':''))}}catch(e){status(e.message,true);auto=false;$('#auto').textContent='Непрерывный осмотр'}finally{busy=false;$('#shot').disabled=false}}

let imageUrl=null;async function showResultImage(){if(!selectedResult)return;const blob=await(await api(original?selectedResult.original:selectedResult.overlay)).blob();if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=URL.createObjectURL(blob);$('#overlay').src=imageUrl;$('#toggleOriginal').textContent=original?'Показать маски':'Показать оригинал'}

async function renderResult(r){selectedResult=r;showSeparateResults(r);original=false;await showResultImage();$('#result').hidden=false;$('#elapsed').textContent=r.seconds+' с';$('#frameStamp').textContent='Кадр получен '+new Date(r.received_at).toLocaleTimeString()+' · результат '+new Date(r.finished_at).toLocaleTimeString();$('#modelResults').innerHTML=r.models.map(m=>`<div class="modelRow">${m.key==='rust'?'Ржавчина / UNet++':m.key==='oil'?'Масло / CLIPSeg + YOLO':'Трещины / YOLO'} · ${m.error?esc(m.error):esc(m.percent)+'% кадра · '+esc(m.seconds)+' с'}</div>`).join('')}

$('#toggleOriginal').onclick=()=>{original=!original;showResultImage().catch(e=>status(e.message,true))};

let liveSession=null;
function endLive(){
 liveSession?.abort();liveSession=null;auto=false;
 showFrameFindings(null);$('#insideLive').textContent='Непрерывный осмотр';$('#gpuOverlay').hidden=true;$('#auto').textContent='Непрерывный осмотр';
 $('#auto').setAttribute('aria-pressed','false');
}
$('#auto').onclick=async()=>{
 if(liveSession){stopCamera();status('Непрерывный осмотр остановлен.');return}
 if(!tag){status('Сначала сфотографируйте QR насоса или выберите насос из списка.',true);return}
 if(busy)return;
 const session=new AbortController();liveSession=session;auto=true;
 $('#insideLive').textContent='Остановить осмотр';$('#auto').textContent='Остановить осмотр';$('#auto').setAttribute('aria-pressed','true');
 try{
  if(!stream){
   if(!navigator.mediaDevices?.getUserMedia)throw Error('Для камеры нужен доверенный HTTPS.');
   const camera=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
   if(session.signal.aborted){camera.getTracks().forEach(t=>t.stop());return}
   stream=camera;$('#video').srcObject=camera;await $('#video').play();
  }
  if(session.signal.aborted)return;
  $('#cameraStart').textContent='Выключить камеру';$('#cameraMode').textContent='AR';$('#cameraPlaceholder').hidden=true;$('#liveBadge').hidden=false;
  while(!session.signal.aborted){
   if(!$('#video').videoWidth){await sleep(100);continue}
   const t=performance.now();const body=await frame(640);
   const gaugeMode=$('#gaugeMode').checked, bodyMode=$('#bodyMode').checked;
   const r=await fetch(bodyMode?'/api/ar-frame?mode=body':gaugeMode?'/api/ar-frame?mode=gauge':'/api/ar-frame',{method:'POST',body,signal:session.signal,headers:{'X-Access-Key':access,Accept:'application/json'}});
   if(session.signal.aborted)return;
   if(r.status===429||r.status>=500){showFrameFindings(null,'Ожидание GPU…');$('#gpuOverlay').hidden=true;status('Ожидание GPU · повтор через секунду');await sleep(1000);continue}
   if(!r.ok){if(r.status===401)$('#access').hidden=false;throw Error((await r.json()).error||'Ошибка обработки кадра')}
   const packet=(r.headers.get('content-type')||'').includes('json')?await r.json():null;
   const url=packet?'data:image/jpeg;base64,'+packet.image:URL.createObjectURL(await r.blob());
   try{
    const img=new Image();img.src=url;await img.decode();
    if(session.signal.aborted)return;
    const c=$('#gpuOverlay');c.width=img.width;c.height=img.height;c.getContext('2d').drawImage(img,0,0);c.hidden=false;if(bodyMode){showFrameFindings(null,bodyLabel(packet?.structure))}else if(gaugeMode){
     const rows=packet?.gauges||[];
     const label=rows.length===1&&rows[0].status==='read'
       ? 'Манометр · '+Number(rows[0].reading).toLocaleString('ru-RU')+' кПа'
       : rows.length?'Манометр · требуется проверка':'Манометр не найден · поднесите камеру ближе';
     showFrameFindings(null,label);
    }else showFrameFindings(packet?.findings,'Сервер передал только маску');
   }finally{if(!packet)URL.revokeObjectURL(url)}
   status(tag+' · непрерывный осмотр · '+((performance.now()-t)/1000).toFixed(2)+' с/кадр');
  }
 }catch(e){if(liveSession===session){stopCamera();status(e.message,true)}}
};

async function historyList(){if(!tag)return;try{const rows=await json('/api/history?tag='+encodeURIComponent(tag));$('#history').replaceChildren();if(!rows.length){$('#history').textContent='Пока нет осмотров.';return}for(const r of rows){const el=document.createElement('div');el.className='historyItem';const time=document.createElement('strong');time.textContent=new Date(r.created_at).toLocaleString('ru-RU');el.append(time);const small=document.createElement('small');small.textContent='Кадр '+r.frame_id+' · требует подтверждения';el.append(small);if(r.observations?.overlay){const b=document.createElement('button');b.textContent='Открыть кадр';b.onclick=()=>renderResult(r.observations).catch(e=>status(e.message,true));el.append(b)}$('#history').append(el)}}catch(e){$('#history').textContent=e.message}}

$('#refreshHistory').onclick=historyList;document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera()});addEventListener('pagehide',stopCamera);init();







$('#gallery').onclick=()=>{

  if(busy)return;

  if(!tag){status('Сначала выберите насос по QR или из списка.',true);return}

  $('#galleryFile').click()

};

$('#galleryFile').onchange=$('#equipmentFile').onchange;

function showSeparateResults(result){

  const container=$('#separateResults');

  container.replaceChildren();

  const names={rust:'Ржавчина',oil:'Масло',crack:'Трещины'};

  for(const model of result.models){

    if(!model.image)continue;

    const figure=document.createElement('figure');

    const link=document.createElement('a');

    const image=document.createElement('img');

    const caption=document.createElement('figcaption');

    link.href=model.image;

    link.target='_blank';

    link.rel='noopener';

    image.src=model.image;

    image.alt=names[model.key]+' — открыть отдельный результат';

    image.style.width='100%';

    caption.textContent=names[model.key]+' · '+(model.percent===0?'маска пуста':model.percent+'% кадра');

    link.append(image);

    figure.append(caption,link);

    container.append(figure);

  }

}

