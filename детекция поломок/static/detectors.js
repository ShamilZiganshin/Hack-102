'use strict';
const $=s=>document.querySelector(s);
const names={hybrid:'YOLO + Qwen',crack_n:'OpenSistemas YOLOv8n-seg',crack_m:'OpenSistemas YOLOv8m-seg',industrial:'Industrial crack',pipeline:'Intel pipeline'};
const notes={hybrid:'На итоговой маске только подтверждения Qwen. Проверка может ошибаться; это не экспертное заключение. Снижение порога требует нового запуска, чтобы проверить дополнительные кандидаты.',crack_n:'Быстрый детектор без проверки: может принимать швы, рёбра и складки за трещины.',crack_m:'Более крупный детектор без проверки Qwen.',industrial:'Другой сегментатор. Возможны многочисленные лишние выделения.',pipeline:'Детектор дефектов труб с рамками, без пиксельной маски.'};
const decisionLabels={confirmed:'Подтверждено Qwen',rejected:'Отклонено Qwen',uncertain:'Сомнительно',not_reviewed:'Не проверено'};
const query=new URLSearchParams(location.search);
let engine=Object.hasOwn(names,query.get('engine'))?query.get('engine'):'hybrid';
let sample='02',file=null,current=null,base='',view='overlay',original=null,masks=[],job=null,renderVersion=0;
const externalRows={};
const isDefect=d=>!['background','gas-pipelines'].includes(d.class);
const isConfirmed=d=>d.verification?.decision==='confirmed';
function error(s){$('#error').textContent=s||''}
function loadImage(src){return new Promise((resolve,reject)=>{let im=new Image;im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Не удалось загрузить изображение'));im.src=src})}
function setBusy(flag){$('#busy').classList.toggle('show',flag);for(let id of ['run','engine','upload','threshold'])$('#'+id).disabled=flag}
function clearResult(){current=null;original=null;masks=[];$('#reviewpanel').hidden=true;$('#count').textContent='—';$('#area').textContent='—';$('#seconds').textContent='—';$('#detections').textContent='Ожидает анализа';$('#maskdl').disabled=true;$('#overlaydl').disabled=true;$('#jsondl').removeAttribute('href')}
async function show(r,prefix){
 const version=++renderVersion;const loadedOriginal=await loadImage(prefix+'original.jpg');
 const loadedMasks=r.task==='segment'?await Promise.all(r.detections.map(async(d,i)=>{if(!isDefect(d))return null;let im=await loadImage(prefix+`mask_${i}.png`);let c=document.createElement('canvas');c.width=im.width;c.height=im.height;let ctx=c.getContext('2d');ctx.drawImage(im,0,0);return {index:i,data:ctx.getImageData(0,0,c.width,c.height).data}})):[];
 if(version!==renderVersion)return;current=r;base=prefix;original=loadedOriginal;masks=loadedMasks.filter(Boolean);engine=r.key||engine;$('#engine').value=engine;
 $('#canvas').hidden=false;$('#empty').hidden=true;$('#masktab').disabled=r.task!=='segment';$('#maskdl').disabled=r.task!=='segment';$('#overlaydl').disabled=false;$('#candidatestab').hidden=r.key!=='hybrid';
 if(r.task!=='segment'&&view==='mask')view='boxes';if(r.key!=='hybrid'&&view==='candidates')view='overlay';
 if(r.verification)$('#threshold').value=Math.round(r.verification.candidate_threshold*100);
 $('#filename').textContent=`${r.model} · ${sample?'фото '+sample:'ваша фотография'} · ${r.imgsz||640} px`;$('#size').textContent=r.size.join(' × ');$('#seconds').textContent=r.seconds.toFixed(1)+' с';$('#modelnote').textContent=notes[engine]||'';$('#jsondl').href=base+'result.json';renderAudit();render();
}
function renderAudit(){
 $('#reviewpanel').hidden=!current?.verification;if(!current?.verification)return;
 const v=current.verification;$('#reviewcounts').textContent=`Кандидатов: ${v.candidate_count} · подтверждено: ${v.confirmed} · отклонено: ${v.rejected} · сомнительно: ${v.uncertain}${v.errors?.length?' · есть ошибки проверки':''}`;
 $('#reviews').replaceChildren();
 for(const d of current.detections){if(!isDefect(d)||d.confidence<v.candidate_threshold)continue;let div=document.createElement('div');div.className='finding';let heading=document.createElement('b');heading.textContent=`Область ${d.candidate_id} · ${decisionLabels[d.verification?.decision]||'Не проверено'}`;let p=document.createElement('p');p.textContent=d.verification?.evidence||'Нет ответа';div.append(heading,p);$('#reviews').append(div)}
 for(const message of v.errors||[]){let p=document.createElement('p');p.className='error';p.textContent=message;$('#reviews').append(p)}
}
function notice(chosen){
 if(!current.verification)return chosen.length?'Предложения YOLO без проверки Qwen. Швы и рёбра могут быть ложными выделениями.':'Выделений выше порога нет; это не доказывает отсутствие повреждений.';
 const v=current.verification;if(view==='candidates')return 'СРАВНЕНИЕ: показаны все кандидаты YOLO, включая отклонённые и сомнительные. На итоговую маску и экспорт они не попадут.';
 if(v.status==='partial')return `Проверка неполная: часть ответов Qwen не получена. Показаны только явные подтверждения (${chosen.length}). Непроверенные области скрыты; причины — в отчёте.`;
 if(v.status==='no_candidates')return 'YOLO не предложила областей при выбранном пороге. Qwen не вызывалась. Это не подтверждение исправности.';
 let extra=(+$('#threshold').value/100<v.candidate_threshold)?' Порог снижен: для проверки дополнительных кандидатов запустите анализ заново.':'';
 return `На фото ${chosen.length} областей, подтверждённых Qwen. Отклонено ${v.rejected}, сомнительно ${v.uncertain}; они скрыты. Подтверждение модели не заменяет осмотр специалиста.`+extra;
}
function render(){
 if(!current||!original)return;let c=$('#canvas');c.width=original.width;c.height=original.height;let ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(original,0,0);
 const threshold=+$('#threshold').value/100,alpha=+$('#alpha').value/100;$('#tv').textContent=threshold.toFixed(2);$('#av').textContent=Math.round(alpha*100)+'%';
 const hybrid=current.key==='hybrid',allCandidates=hybrid&&view==='candidates';
 const chosen=current.detections.map((d,index)=>({...d,index})).filter(d=>isDefect(d)&&d.confidence>=threshold&&(!hybrid||allCandidates||isConfirmed(d)));
 const indices=new Set(chosen.map(d=>d.index));let union=new Uint8Array(c.width*c.height);
 for(const m of masks)if(indices.has(m.index))for(let j=0,k=0;j<union.length;j++,k+=4)if(m.data[k]>127)union[j]=1;
 let pixels=ctx.getImageData(0,0,c.width,c.height),count=0;
 for(let j=0,k=0;j<union.length;j++,k+=4){if(union[j])count++;if(view==='mask'){pixels.data[k]=pixels.data[k+1]=pixels.data[k+2]=union[j]?255:0}else if((view==='overlay'||view==='candidates')&&union[j]){let color=allCandidates?[75,155,255]:[255,91,45];for(let channel=0;channel<3;channel++)pixels.data[k+channel]=Math.round(pixels.data[k+channel]*(1-alpha)+color[channel]*alpha)}}
 if(['mask','overlay','candidates'].includes(view))ctx.putImageData(pixels,0,0);
 if(view==='boxes'||(current.task!=='segment'&&view==='overlay')){ctx.lineWidth=Math.max(2,c.width/400);ctx.font=Math.max(13,c.width/55)+'px sans-serif';ctx.strokeStyle='#ff9a60';ctx.fillStyle='#ff9a60';for(const d of chosen){let [a,b,c,e]=d.box;ctx.strokeRect(a,b,c-a,e-b);ctx.fillText(hybrid?'Qwen '+d.candidate_id:d.class+' '+d.confidence.toFixed(2),a,Math.max(18,b-5))}}
 $('#count').textContent=chosen.length;$('#area').textContent=current.task==='segment'?(count/union.length*100).toFixed(2)+'%':'Нет маски';$('#notice').textContent=notice(chosen);
 $('#detections').replaceChildren();if(!chosen.length)$('#detections').textContent=hybrid?'Подтверждённых выделений нет.':'Нет выделений выше порога.';
 for(const d of chosen){let div=document.createElement('div');div.textContent=hybrid?`Область ${d.candidate_id} · ${allCandidates?'кандидат YOLO':decisionLabels[d.verification.decision]}`:`${d.class==='crack'?'Трещина':d.class}: ${d.confidence.toFixed(3)}`;$('#detections').append(div)}
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
}
async function previewSample(id){
 const version=++renderVersion;clearResult();let im=await loadImage(id.startsWith('e')?`/test-photos/${id}.jpg`:`/samples/${id}.jpg`);if(version!==renderVersion)return;
 let c=$('#canvas');c.width=im.width;c.height=im.height;c.getContext('2d').drawImage(im,0,0);c.hidden=false;$('#empty').hidden=true;$('#filename').textContent=externalRows[id]?.title||'Фото '+id;$('#notice').textContent=engine==='hybrid'?'Нажмите «Выделить повреждение»: YOLO найдёт области, затем Qwen проверит каждую.':'Для этой модели пример ещё не обработан. Нажмите «Выделить повреждение».';$('#modelnote').textContent=notes[engine];
}
async function demo(id){
 if(job)return;sample=id;file=null;error('');view='overlay';$('#uploadname').textContent='Выбрать или перетащить фото';document.querySelectorAll('.example').forEach(b=>b.classList.toggle('active',b.dataset.id===id));
 try{let response=await fetch(`/api/specialists/${engine}/${id}`);if(response.status===404){await previewSample(id);return}let data=await response.json();if(!response.ok)throw new Error(data.error||'Ошибка загрузки примера');await show(data,`/specialist-files/${engine}/${id}/`)}catch(e){error(e.message)}
}
function choose(f){if(!f||job)return;renderVersion++;file=f;sample=null;clearResult();$('#uploadname').textContent=f.name;let url=URL.createObjectURL(f);loadImage(url).then(im=>{let c=$('#canvas');c.width=im.width;c.height=im.height;c.getContext('2d').drawImage(im,0,0);c.hidden=false;$('#empty').hidden=true;URL.revokeObjectURL(url)}).catch(e=>error(e.message));$('#filename').textContent=f.name;$('#notice').textContent='Фото выбрано. Нажмите «Выделить повреждение».';error('')}
$('#engine').value=engine;$('#engine').onchange=()=>{engine=$('#engine').value;view='overlay';if(sample)demo(sample);else{clearResult();$('#modelnote').textContent=notes[engine];$('#notice').textContent='Модель изменена. Запустите новый анализ.'}};
$('#upload').onchange=e=>choose(e.target.files[0]);['dragover','drop'].forEach(name=>$('#drop').addEventListener(name,e=>{e.preventDefault();if(name==='drop')choose(e.dataTransfer.files[0])}));
$('#threshold').oninput=render;$('#alpha').oninput=render;document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;render()});
$('#run').onclick=async()=>{
 if(job||(!file&&!sample))return;error('');setBusy(true);
 try{let form=new FormData;form.append('engine',engine);form.append('candidate_threshold',(+$('#threshold').value/100).toFixed(2));if(file)form.append('image',file);else form.append('example',sample);let response=await fetch('/api/jobs',{method:'POST',body:form});let data=await response.json();if(!response.ok)throw new Error(data.error||'Ошибка запуска');job=data.id;history.replaceState(null,'',`/detectors?engine=${engine}&job=${job}`);poll()}catch(e){error(e.message);finish()}
};
function finish(){job=null;setBusy(false)}
async function poll(){
 try{let response=await fetch('/api/jobs/'+job);let data=await response.json();if(!response.ok)throw new Error(data.error||'Ошибка чтения задания');const stage={queued:'Ожидает своей очереди',detecting:'YOLO ищет кандидатов',verifying:'Qwen проверяет найденные области',finalizing:'Собираем подтверждённую маску',analyzing:'Подготавливаем модель',generating:'Модель составляет ответ'};$('#busy b').textContent=stage[data.status]||'Обработка';$('#progress').textContent=`Прошло ${Math.round(data.elapsed||0)} с${data.total?` · проверено ${data.reviewed||0} из ${data.total} · группа ${data.batch||1}/${data.batch_total||1}`:''}${data.tokens?' · ответ формируется':''}`;
 if(data.status==='completed'){view='overlay';await show(data.result,`/files/${data.id}/`);finish();return}if(data.status==='error')throw new Error(data.error);setTimeout(poll,1500)}catch(e){error(e.message);finish()}
}
function downloadCanvas(canvas,name){canvas.toBlob(blob=>{let link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)},'image/png')}
$('#overlaydl').onclick=()=>{if(!current)return;let before=view;view='overlay';render();downloadCanvas($('#canvas'),'confirmed_damage_overlay.png');view=before;render()};
$('#maskdl').onclick=()=>{if(!current||current.task!=='segment')return;let before=view;view='mask';render();downloadCanvas($('#canvas'),'confirmed_damage_mask.png');view=before;render()};
function addExample(id,title,target,src,kind){let button=document.createElement('button');button.className='example';button.dataset.id=id;let image=document.createElement('img');image.src=src;image.alt=title;let text=document.createElement('span');text.textContent=title;if(kind){let small=document.createElement('small');small.textContent=kind==='control'?'Контроль ложных тревог':'Видимое повреждение';text.append(small)}button.append(image,text);button.onclick=()=>demo(id);$(target).append(button)}
async function init(){
 for(const [id,title] of [['01','Фото 1 · разрыв корпуса'],['02','Фото 2 · трещина трубы'],['03','Фото 3 · изоляция'],['casing','Ваш корпус · рёбра и швы']])addExample(id,title,'#examples',`/samples/${id}.jpg`);
 try{let rows=await(await fetch('/api/test-photos')).json();for(const row of rows){externalRows[row.id]=row;addExample(row.id,row.title,'#externalExamples',`/test-photos/${row.id}.jpg`,row.kind)}}catch(e){error(e.message)}
 const requested=query.get('job');if(requested&&/^[a-f0-9]{16}$/.test(requested)){sample=null;file=null;job=requested;setBusy(true);poll()}else await demo(query.get('sample')==='casing'?'casing':'02');
}
init();
