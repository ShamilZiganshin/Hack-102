const trendPump=document.querySelector('#pump,#equipment');
async function trends(){
 const tag=trendPump.value,demo=document.querySelector('#demo').checked;if(!tag)return;
 try{const url='/api/trends?tag='+encodeURIComponent(tag)+'&demo='+Number(demo);
 const r=await api(url);if(!r.ok)throw Error();const rows=await r.json();
 if(tag!==trendPump.value||demo!==document.querySelector('#demo').checked)return;
 document.querySelector('#trendSource').textContent=(demo?'Демонстрационные данные · '+['Штатный режим','Перегрев','Низкое давление','Вибрация и перегрузка'][Number(tag.slice(-1))-1]:'Измерения датчиков')+' · '+(rows.length?'последняя точка '+new Date(rows.at(-1).tick*1000).toLocaleTimeString():'нет измерений')+(demo&&rows.length?' · Вибрационный архив Excel: '+rows.at(-1).time+' · ускоренное воспроизведение':'');
 const plots=document.querySelector('#plots');plots.replaceChildren();
 for(const [i,[label,unit,min,max]] of [['Температура','°C',10,75],['Вибрация','мм/с',0,4.5],['Давление','бар',2,10],['Ток','А',0,25],['СКЗ · архив','мм/с',null,null],['Гармоника 1×','мм/с',null,2.8],['Гармоника 2×','мм/с',null,1.8],['ВЧ-шум','g',null,2.5]].entries()){
 for(const row of rows)if(row.vals.length===4)row.vals.push(row.rms,row.x1,row.x2,row.hf);
 const pts=rows.filter(row=>row.vals[i]!=null);if(!pts.length)continue;
 const vals=pts.map(row=>Number(row.vals[i])),last=vals.at(-1);
 const lo=Math.min(...vals,...(demo&&min!=null?[min]:[])),hi=Math.max(...vals,...(demo&&max!=null?[max]:[]));
 const y=v=>90-(v-lo)/(hi-lo||1)*80;
 const points=pts.map((row,k)=>[(row.tick-rows.at(-1).tick+600)/600*300,y(vals[k])].join(',')).join(' ');
 const fig=document.createElement('figure'),caption=document.createElement('figcaption');
 caption.textContent=label+' · '+last+' '+unit+(demo?(min!=null&&last<min?' ↓ Ниже':max!=null&&last>max?' ↑ Выше':min==null&&max==null?'':' · В диапазоне'):'');
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 300 100');
 function line(points,color){const l=document.createElementNS(svg.namespaceURI,'polyline');l.setAttribute('points',points);l.setAttribute('stroke',color);l.setAttribute('fill','none');l.setAttribute('stroke-width','2');svg.append(l)}
 if(demo)for(const bound of [min,max].filter(v=>v!=null))line('0,'+y(bound)+' 300,'+y(bound),'#55727a');
 line(points,demo&&((min!=null&&last<min)||(max!=null&&last>max))?'#ffa767':'#60dece');fig.append(caption,svg);plots.append(fig)
 }
 }catch{if(tag===trendPump.value){document.querySelector('#plots').replaceChildren();document.querySelector('#trendSource').textContent='История недоступна'}}
}
setInterval(trends,5000);

trendPump.addEventListener('change',trends);document.querySelector('#demo').addEventListener('change',trends);
