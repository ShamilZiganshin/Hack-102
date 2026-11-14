const $=s=>document.querySelector(s);
const roles={worker:'Работник',brigadir:'Начальник цеха',admin:'Администратор'};
const states={open:'Открыт',review:'Исправлено работником · на проверке',fixed:'Ремонт подтверждён',unfixed:'Не исправлено'};
let me,before;
function el(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e}
function run(fn){return async e=>{e?.preventDefault();$('#msg').textContent='';try{await fn(e)}catch(err){$('#msg').textContent=err.message}}}
async function api(path,data){const r=await fetch('/api/field/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Field-Request':'1'},body:JSON.stringify(data)});const v=await r.json();if(!r.ok){if(r.status===401&&me)location.assign('/login');throw Error(v.error)}return v}
function button(parent,text,fn){const b=el('button',text);b.type='button';b.onclick=run(fn);parent.append(b);return b}
$('#signin').onsubmit=run(async e=>{const u=await api('login',Object.fromEntries(new FormData(e.target)));location.replace('/'+u.role)});
$('#logout').onclick=run(async()=>{await api('logout',{});location.replace('/login')});
function edit(u={}){const f=$('#editor');f.hidden=false;for(const [k,v] of Object.entries({id:u.id||'',login:u.login||'',role:u.role||'worker',password:''}))f.elements[k].value=v;f.elements.password.required=!u.id;f.elements.login.focus()}
async function users(){const box=$('#users');box.replaceChildren();for(const u of await api('users')){const p=el('p',u.login+' · '+roles[u.role]+' ');button(p,'Изменить',()=>edit(u));if(me.id!==u.id)button(p,'Удалить',async()=>{if(confirm('Удалить пользователя '+u.login+'?')){await api('users',{id:u.id,op:'delete'});await users()}});box.append(p)}}
$('#newUser').onclick=()=>edit();$('#editor').onsubmit=run(async e=>{const d=Object.fromEntries(new FormData(e.target));d.id=Number(d.id)||null;await api('users',d);if(d.id===me.id){location.replace('/login');return}e.target.hidden=true;await users()});
async function list(reset=true){if(reset){before=null;$('#records').replaceChildren()}const rows=await api('records'+(before?'?before='+before:''));$('#more').hidden=rows.length!==50;if(!before&&!rows.length)$('#records').append(el('p','Осмотров пока нет.'));
 for(const r of rows){before=r.id;const card=el('article');card.append(el('h3',r.tag+' · '+states[r.state]),el('small',new Date(r.created_at).toLocaleString('ru-RU')+' · '+r.author));if(r.has_photo){const a=el('a');a.href='/api/field/records/'+r.id+'/photo';a.target='_blank';const img=el('img');img.alt='Снимок осмотра '+r.tag;img.loading='lazy';img.src=a.href;a.append(img);card.append(el('p'),a);const download=el('a','Скачать фото');download.href=a.href;download.download=r.tag+'-'+r.id+'.jpg';card.append(el('p'),download)}else card.append(el('p','Архивный снимок недоступен'));
 if(r.note)card.append(el('p',r.note));const d=el('details'),summary=el('summary','Комментарии и изменения');d.append(summary);d.ontoggle=run(async()=>{if(!d.open)return;const rows=await api('records/'+r.id+'/events');d.replaceChildren(summary,...rows.map(v=>el('p',new Date(v.created_at).toLocaleString('ru-RU')+' · '+v.actor+' · '+states[v.state]+(v.comment?' — '+v.comment:''))))});card.append(d);
 const comment=el('textarea');comment.placeholder='Комментарий к ремонту';comment.maxLength=2000;card.append(comment);const actions=el('div');actions.className='row';card.append(actions);
 async function save(data){await api('records/'+r.id,{version:r.version,comment:comment.value,...data});await list()}
 button(actions,'Добавить комментарий',()=>{if(!comment.value.trim())throw Error('Введите комментарий');return save({})});
 if(me.role==='worker'&&['open','unfixed'].includes(r.state))button(actions,'Исправлено · на проверку',()=>save({state:'review'}));
 if(me.role==='brigadir'){button(actions,'Подтвердить ремонт',()=>save({state:'fixed'}));button(actions,'Не исправлено',()=>save({state:'unfixed'}))}
 if(me.role==='admin'){const select=el('select');for(const [v,t] of Object.entries(states)){const op=el('option',t);op.value=v;select.append(op)}select.value=r.state;const note=el('input');note.placeholder='Описание записи';note.value=r.note;actions.append(select,note);button(actions,'Сохранить запись',()=>save({state:select.value,note:note.value}));button(actions,'Удалить запись',()=>{if(confirm('Удалить снимок и запись?'))return save({op:'delete'})})}
 $('#records').append(card)}}
$('#more').onclick=run(()=>list(false));
run(async()=>{if(location.pathname==='/login'){$('#login').hidden=false;return}me=await api('me');$('#who').textContent=me.login;$('#title').textContent=roles[me.role];$('#cab').hidden=false;$('#camera').hidden=me.role==='brigadir';if(me.role==='admin'){$('#accounts').hidden=false;await users()}await list()})();
