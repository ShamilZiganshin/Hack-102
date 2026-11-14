const cameraView=document.querySelector('.camera .view');
const fullButton=document.querySelector('#fullCamera');
function fullState(){
 const expanded=!!document.fullscreenElement||cameraView.classList.contains('expanded');
 fullButton.textContent=expanded?'✕ Выйти':'⛶ На весь экран';
 fullButton.setAttribute('aria-pressed',String(expanded));
 document.body.classList.toggle('cameraExpanded',expanded);
}
async function toggleView(){
 if(document.fullscreenElement){await document.exitFullscreen();return}
 if(cameraView.classList.contains('expanded'))cameraView.classList.remove('expanded');
 else{
  try{if(!cameraView.requestFullscreen)throw Error();await cameraView.requestFullscreen()}
  catch{cameraView.classList.add('expanded')}
 }
 fullState();
}
fullButton.onclick=toggleView;
document.addEventListener('fullscreenchange',fullState);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&cameraView.classList.contains('expanded'))toggleView()});
function cameraReadings(data){
 const panel=document.querySelector('#cameraReadings');
 panel.replaceChildren();panel.hidden=!data;
 if(!data)return;
 const labels={temperature_c:'T',vibration_mm_s:'СКЗ',pressure_out_bar:'P',current_a:'I'};
 const vals=data.metrics.filter(m=>labels[m.metric]&&m.value!=null).map(m=>labels[m.metric]+' '+Number(m.value).toLocaleString('ru-RU')+' '+m.unit);
 const line=document.createElement('div');line.textContent=[data.tag,data.demo?'Демо':'Датчики',...vals].join(' · ');panel.append(line);
 if(data.stale){const note=document.createElement('small');note.textContent='Нет свежих показаний';panel.append(note)}
 const actions={'Амплитуда 1×':'Проверить рабочее колесо','Амплитуда 2×':'Проверить центровку','ВЧ-шум':'Повторить замер спектра','Температура датчика':'Сверить температуру','Давление на выходе':'Сверить манометр','Ток':'Проверить нагрузку','Виброскорость':'Повторить замер вибрации'};
 for(const alert of data.alerts||[]){
  const row=document.createElement('div');row.className='miniAlert';
  row.textContent='ALERT · '+alert.label+' '+(alert.direction==='ниже'?'↓':'↑')+' '+alert.value+' '+alert.unit+' · '+(actions[alert.label]||alert.advice);panel.append(row);
 }
}
