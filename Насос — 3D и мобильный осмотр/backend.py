from pathlib import Path
import sys,os,json,time,math,uuid,re,ssl,threading,subprocess,io,socket,secrets,hashlib,urllib.request
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,unquote
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from PIL import Image,ImageOps
import numpy as np
import zxingcpp
PUBLIC=ROOT/'public'; PRIVATE=ROOT/'private'; OUT=ROOT/'outputs'
CONFIG=json.loads((PRIVATE/'config.json').read_text(encoding='utf-8'))
JOBS={};LOCK=threading.Lock();WORKERS={};POOL=ThreadPoolExecutor(2)
def db():return psycopg.connect(CONFIG['database'],row_factory=dict_row,connect_timeout=5)
def now():return datetime.now(timezone.utc).isoformat()
def passport(tag):
 with db() as c:
  row=c.execute('SELECT * FROM v_equipment_passport WHERE tag=%s',(tag,)).fetchone()
  if not row:return None
  row['limits']=c.execute("SELECT l.*,d.filename FROM equipment_limits l LEFT JOIN documents d ON d.id=l.source_document_id WHERE equipment_id=%s AND status='approved'",(row['equipment_id'],)).fetchall()
  row['documents']=c.execute('SELECT d.id,d.filename,d.mime_type FROM equipment_documents ed JOIN documents d ON d.id=ed.document_id WHERE equipment_id=%s ORDER BY d.id',(row['equipment_id'],)).fetchall()
  row['maintenance']=c.execute("SELECT * FROM v_maintenance_due WHERE tag=%s AND status='approved'",(tag,)).fetchall()
  return row
METRICS={'temperature_c':('Температура датчика','°C'),'vibration_mm_s':('Виброскорость','мм/с'),'pressure_out_bar':('Давление на выходе','бар'),'current_a':('Ток','А'),'operating_hours':('Наработка','ч')}
def telemetry(tag,demo=False):
 p=passport(tag)
 if not p:return None
 if demo:
  t=time.time();scenario=int(tag[-1]);base={1:(53,2.1,6.5,18),2:(88,2.8,6.4,19),3:(62,7.2,5.2,22),4:(96,9.1,11.8,29)}[scenario]
  m={'measured_at':now(),'data_origin':'simulator','temperature_c':round(base[0]+1.5*math.sin(t/15),1),'vibration_mm_s':round(base[1]+.25*math.sin(t/11),2),'pressure_out_bar':round(base[2]+.2*math.sin(t/19),2),'current_a':round(base[3]+.4*math.sin(t/8),2),'operating_hours':round(1200+(t-CONFIG['demo_epoch'])/3600,2)}
  with db() as c:p['limits']=c.execute("SELECT * FROM equipment_limits WHERE equipment_id=%s AND status='demo'",(p['equipment_id'],)).fetchall()
 else:
  with db() as c:m=c.execute('SELECT measurement FROM v_equipment_latest_measurement WHERE tag=%s',(tag,)).fetchone()['measurement']
 limits={x['metric']:x for x in p['limits']}
 stale=True if not m else (datetime.now(timezone.utc)-datetime.fromisoformat(str(m['measured_at']).replace('Z','+00:00'))).total_seconds()>30
 cells=[]
 for key,(label,unit) in METRICS.items():
  value=m.get(key) if m else None;l=limits.get(key);state='no_data' if value is None else 'no_limit'
  if value is not None and l:
   state='outside' if (l['lower_bound'] is not None and value<float(l['lower_bound'])) or (l['upper_bound'] is not None and value>float(l['upper_bound'])) else 'within'
  if stale and value is not None:state='stale'
  cells.append({'metric':key,'label':label,'unit':unit,'value':value,'state':state,'limit':l})
 return {'tag':tag,'demo':demo,'scenario':{1:'Штатный режим',2:'Перегрев и ржавчина',3:'Масло и вибрация',4:'Несколько отклонений'}[int(tag[-1])] if demo else None,'source':'Симулятор • не датчики' if demo else (m.get('data_origin','unknown') if m else 'Нет измерений в БД'),'measured_at':m.get('measured_at') if m else None,'server_at':now(),'stale':stale,'metrics':cells}
class Worker:
 def __init__(self,key):
  self.key=key;self.ready=False;self.error=None;self.lock=threading.Lock()
  try:
   folder='детекция ржавчины' if key=='rust' else 'детекция масла'
   self.log=open(OUT/(key+'-worker.log'),'ab')
   self.p=subprocess.Popen([str(ROOT.parent/folder/'.venv/Scripts/python.exe'),'-u',str(ROOT/'worker.py'),key],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',creationflags=0x08000000)
   r=json.loads(self.p.stdout.readline());self.ready=r.get('ready')==key
  except Exception as e:self.error=str(e)
 def infer(self,image,mask,mode):
  with self.lock:
   if not self.ready:raise RuntimeError(self.error or 'Модель загружается')
   self.p.stdin.write(json.dumps({'image':str(image),'mask':str(mask),'mode':mode})+'\n');self.p.stdin.flush()
   r=json.loads(self.p.stdout.readline())
   if 'error' in r:raise RuntimeError(r['error'])
   return r
def warm(key):WORKERS[key]=Worker(key)
def crack_hybrid(image,out,job):
 boundary='----Kiber'+uuid.uuid4().hex
 body=(f'--{boundary}\r\nContent-Disposition: form-data; name="engine"\r\n\r\nhybrid\r\n--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="frame.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+image.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 req=urllib.request.Request('http://127.0.0.1:8767/api/jobs',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
 remote=json.load(opener.open(req,timeout=15));job['crack_job']=remote['id'];start=time.perf_counter()
 while time.perf_counter()-start<1200:
  r=json.load(opener.open('http://127.0.0.1:8767/api/jobs/'+remote['id'],timeout=15));job['crack_progress']={k:r.get(k) for k in ('status','tokens','reviewed','total','elapsed')}
  if r['status']=='error':raise RuntimeError(r['error'])
  if r['status']=='completed':
   mask=opener.open('http://127.0.0.1:8767/files/'+remote['id']+'/mask.png',timeout=15).read();(out/'crack.png').write_bytes(mask)
   report=r['result'];return {'key':'crack','model':report['model'],'seconds':report['seconds'],'percent':round(report['mask_percent_of_image'],3),'verification':report['verification'],'remote_job':remote['id']}
  time.sleep(1)
 raise TimeoutError('Проверка трещин превысила 20 минут; задание остаётся в InspectLab.')
def analyze(id,image,tag,mode,captured,cracks):
 job=JOBS[id];job.update(status='running');t=time.perf_counter();out=OUT/id
 try:
  fs={k:POOL.submit(WORKERS[k].infer,image,out/(k+'.png'),mode) for k in ('rust','oil')}
  results=[]
  for k,f in fs.items():
   try:results.append(f.result(timeout=150))
   except Exception as e:results.append({'key':k,'error':str(e)})
  job.update(models=results,stage='surface_done')
  if cracks:
   job['stage']='crack_hybrid'
   try:results.append(crack_hybrid(image,out,job))
   except Exception as e:results.append({'key':'crack','error':str(e)})
  rgb=np.array(Image.open(image).convert('RGB'));blend=rgb.copy()
  for r in results:
   if 'error' not in r:
    mask=np.array(Image.open(out/(r['key']+'.png')))>0
    if mask.shape!=rgb.shape[:2]:raise ValueError('Размер маски не совпадает с кадром')
    color=np.array({'rust':[255,100,45],'oil':[49,211,225],'crack':[235,65,175]}[r['key']])
    blend[mask]=np.round(rgb[mask]*.55+color*.45).astype('uint8')
  Image.fromarray(blend).save(out/'overlay.jpg',quality=92)
  job.update(status='done',models=results,seconds=round(time.perf_counter()-t,2),finished_at=now(),overlay='/results/'+id+'/overlay.jpg',original='/results/'+id+'/frame.jpg')
  with db() as c:
   c.execute("INSERT INTO inspections(equipment_id,frame_id,observations,decision,notes) SELECT id,%s,%s,'pending',%s FROM equipment WHERE tag=%s",(id,Jsonb(job),'Автоматическая гипотеза; требуется осмотр. Кадр с телефона / загруженное фото.',tag))
 except Exception as e:job.update(status='error',error=str(e))
 finally:
  (out/'result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8');LOCK.release()
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(PUBLIC),**kw)
 def log_message(self,fmt,*args):print(now(),fmt%args,flush=True)
 def send(self,b,ctype='application/json; charset=utf-8',status=200):
  if not isinstance(b,bytes):b=json.dumps(b,ensure_ascii=False,default=str).encode('utf-8')
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
 def auth(self):
  token=self.headers.get('X-Access-Key','')
  return secrets.compare_digest(token,CONFIG['access_key'])
 def do_GET(self):
  try:self.get()
  except Exception as e:self.send({'error':str(e)},status=500)
 def get(self):
  u=urlparse(self.path);path=unquote(u.path);q=parse_qs(u.query)
  if path=='/api/health':return self.send({'ok':True,'models':{k:{'ready':w.ready,'error':w.error} for k,w in WORKERS.items()}})
  if path.startswith('/api/') and not self.auth():return self.send({'error':'Откройте мобильную страницу по QR подключения или введите код доступа.'},status=401)
  if path=='/api/equipment':
   with db() as c:return self.send(c.execute('SELECT tag,name,serial_no FROM equipment ORDER BY tag').fetchall())
  if path=='/api/passport':
   p=passport(q.get('tag',[''])[0]);return self.send(p or {'error':'Насос не найден'},status=200 if p else 404)
  if path=='/api/telemetry':
   p=telemetry(q.get('tag',[''])[0],q.get('demo',['0'])[0]=='1');return self.send(p or {'error':'Насос не найден'},status=200 if p else 404)
  if path.startswith('/api/jobs/'):
   job=JOBS.get(path.rsplit('/',1)[-1]);return self.send(job or {'error':'Кадр не найден'},status=200 if job else 404)
  if path=='/api/history':
   with db() as c:return self.send(c.execute('SELECT i.id,i.created_at,i.frame_id,i.observations FROM inspections i JOIN equipment e ON e.id=i.equipment_id WHERE e.tag=%s ORDER BY i.created_at DESC LIMIT 12',(q.get('tag',[''])[0],)).fetchall())
  if path.startswith('/api/document/'):
   id=path.rsplit('/',1)[-1]
   if not id.isdigit():return self.send({'error':'Invalid document'},status=400)
   with db() as c:r=c.execute('SELECT content,mime_type FROM documents WHERE id=%s',(int(id),)).fetchone()
   return self.send(bytes(r['content']),r['mime_type']) if r else self.send({'error':'Нет документа'},status=404)
  if path.startswith('/results/'):
   # Results require the access key, even when loaded as an image via fetch.
   if not self.auth():return self.send({'error':'Access key required'},status=401)
   if not re.fullmatch(r'/results/[0-9a-f]{16}/(overlay\.jpg|frame\.jpg|rust\.png|oil\.png|crack\.png)',path):return self.send({'error':'Not found'},status=404)
   f=OUT/Path(path).parts[-2]/Path(path).name
   return self.send(f.read_bytes(),'image/png' if f.suffix=='.png' else 'image/jpeg') if f.exists() else self.send({'error':'Not found'},status=404)
  if path=='/':self.path='/mobile.html'
  return super().do_GET()
 def do_POST(self):
  try:
   if not self.auth():return self.send({'error':'Нужен код доступа'},status=401)
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=12_000_000:return self.send({'error':'Файл должен быть меньше 12 МБ'},status=413)
   body=self.rfile.read(size);u=urlparse(self.path);q=parse_qs(u.query)
   if u.path=='/api/measurements':
    if not secrets.compare_digest(self.headers.get('X-Sensor-Key',''),CONFIG['sensor_key']):return self.send({'error':'Нужен отдельный ключ датчиков'},status=403)
    v=json.loads(body);tag=v['tag'];stamp=datetime.fromisoformat(v['measured_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp.timestamp()>time.time()+60:raise ValueError('Нужна реальная дата измерения с часовым поясом')
    vals=[]
    for k in METRICS:
     n=v.get(k)
     if n is not None and (isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n)):raise ValueError('Некорректное значение '+k)
     vals.append(n)
    if all(x is None for x in vals):raise ValueError('Нет измерений')
    with db() as c:
     r=c.execute('INSERT INTO measurements(equipment_id,measured_at,temperature_c,vibration_mm_s,pressure_out_bar,current_a,operating_hours,data_origin) SELECT id,%s,%s,%s,%s,%s,%s,%s FROM equipment WHERE tag=%s RETURNING id',(stamp,*vals,'sensor_api',tag)).fetchone()
    return self.send(r or {'error':'Насос не найден'},status=201 if r else 404)
   if u.path not in ('/api/qr','/api/analyze'):return self.send({'error':'Not found'},status=404)
   Image.MAX_IMAGE_PIXELS=24_000_000
   im=ImageOps.exif_transpose(Image.open(io.BytesIO(body)));im.load();im=im.convert('RGB')
   if u.path=='/api/qr':
    im.thumbnail((2400,2400));codes=zxingcpp.read_barcodes(im,formats=zxingcpp.BarcodeFormat.QRCode)
    for code in codes:
     text=code.text.strip();tag=text.removeprefix('KIBER102:')
     if text.startswith(('https://','http://')):tag=parse_qs(urlparse(text).query).get('asset',[''])[0]
     if re.fullmatch(r'AMS-PS-00[1-4]',tag) and passport(tag):return self.send({'tag':tag,'raw':text})
    return self.send({'error':'QR насоса не распознан. Поднесите камеру ближе и уберите блики.'},status=422)
   tag=q.get('tag',[''])[0]
   if not passport(tag):return self.send({'error':'Сначала выберите насос по QR'},status=400)
   if not all(WORKERS.get(k) and WORKERS[k].ready for k in ('rust','oil')):return self.send({'error':'Модели ещё загружаются'},status=503)
   if not LOCK.acquire(blocking=False):return self.send({'error':'Сервер занят предыдущим кадром. Повторите после его завершения.'},status=429)
   try:
    im.thumbnail((1280,1280));id=uuid.uuid4().hex[:16];out=OUT/id;out.mkdir();im.save(out/'frame.jpg',quality=92)
    JOBS[id]={'id':id,'tag':tag,'status':'queued','received_at':now(),'capture_at':self.headers.get('X-Captured-At'),'width':im.width,'height':im.height,'models':[]}
    threading.Thread(target=analyze,args=(id,out/'frame.jpg',tag,'quality' if q.get('quality',['0'])[0]=='1' else 'fast256',JOBS[id]['capture_at'],q.get('cracks',['0'])[0]=='1'),daemon=True).start()
   except Exception:LOCK.release();raise
   return self.send({'id':id},status=202)
  except (ValueError,KeyError,Image.UnidentifiedImageError,Image.DecompressionBombError) as e:self.send({'error':str(e)},status=400)
  except Exception as e:self.send({'error':str(e)},status=500)
def main():
 OUT.mkdir(exist_ok=True)
 for key in ('rust','oil'):threading.Thread(target=warm,args=(key,),daemon=True).start()
 http=ThreadingHTTPServer(('0.0.0.0',8769),Handler)
 threading.Thread(target=http.serve_forever,daemon=True).start()
 https=ThreadingHTTPServer(('0.0.0.0',8443),Handler);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(PRIVATE/'server.pem',PRIVATE/'server-key.pem');https.socket=ctx.wrap_socket(https.socket,server_side=True)
 print('HTTP :8769 / HTTPS :8443',flush=True);https.serve_forever()
if __name__=='__main__':main()
