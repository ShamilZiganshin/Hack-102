import base64,gpu_client
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
import demo_trends,recommendations
def telemetry(tag,demo=False):
 p=passport(tag)
 if not p:return None
 if demo:
  if tag not in demo_trends.TAGS:return None
  point=demo_trends.latest(db,tag)
  if not point:return None
  t=point["tick"]
  m=dict(zip(demo_trends.KEYS,point["vals"]),measured_at=datetime.fromtimestamp(t,timezone.utc).isoformat(),data_origin='simulator',operating_hours=round(1200+(t-CONFIG['demo_epoch'])/3600,2))
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
 spectrum={} if stale or not m else (m.get('vibration_spectrum') or {})
 source='Датчики'
 if demo:
  spectrum={k:point[k] for k in ('time','rpm','rms','x1','x2','hf')}
  source='Пример Excel · '+str(spectrum['time'])
 alerts=recommendations.evaluate(spectrum,cells)
 return {'alerts':alerts,'spectrum':spectrum,'spectrum_source':source,'tag':tag,'demo':demo,'scenario':{1:'Штатный режим',2:'Перегрев и ржавчина',3:'Пониженное давление',4:'Вибрация и повышенный ток'}[int(tag[-1])] if demo else None,'source':'Симулятор • не датчики' if demo else (m.get('data_origin','unknown') if m else 'Нет измерений в БД'),'measured_at':m.get('measured_at') if m else None,'server_at':now(),'stale':stale,'metrics':cells}
def analyze(id,image,tag,mode,captured,cracks):
 job=JOBS[id];job.update(status='running');t=time.perf_counter();out=OUT/id
 try:
  answer=json.loads(gpu_client.request('/inspect',image.read_bytes(),**{'X-Quality':str(int(mode=='quality')),'X-Cracks':str(int(cracks))}))
  results=answer['models']
  for name in ['overlay.jpg','rust.png','oil.png']+(['crack.png'] if cracks else []):
   (out/name).write_bytes(base64.b64decode(answer['images'][name],validate=True))
  job.update(status='done',models=results,seconds=round(time.perf_counter()-t,2),finished_at=now(),overlay='/results/'+id+'/overlay.jpg',original='/results/'+id+'/frame.jpg')
  with db() as c:
   c.execute("INSERT INTO inspections(equipment_id,frame_id,observations,decision,notes) SELECT id,%s,%s,'pending',%s FROM equipment WHERE tag=%s",(id,Jsonb(job),'Автоматическая гипотеза; требуется осмотр. Кадр с телефона / загруженное фото.',tag))
 except Exception as e:job.update(status='error',error=str(e))
 finally:
  (out/'result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8');LOCK.release()
class RelayRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None

mobile_http=urllib.request.build_opener(urllib.request.ProxyHandler({}),RelayRedirect())

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(PUBLIC),**kw)
 def log_message(self,fmt,*args):print(now(),fmt%args,flush=True)
 def send(self,b,ctype='application/json; charset=utf-8',status=200,upstream=None):
  if not isinstance(b,bytes):b=json.dumps(b,ensure_ascii=False,default=str).encode('utf-8')
  self.send_response(status)
  if upstream:
   for header in ('Set-Cookie','Location'):
    if upstream.get(header):self.send_header(header,upstream[header])
  self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
 def auth(self):
  token=self.headers.get('X-Access-Key','')
  return secrets.compare_digest(token,CONFIG['access_key'])
 def rtx_mobile(self):
  if not isinstance(self.connection,ssl.SSLSocket):return False
  path=urlparse(self.path).path
  pages={'/login','/worker','/brigadir','/admin','/field.js','/','/mobile.html','/ar.html','/examples.html','/mobile.css','/mobile.js','/camera-view.js','/camera-view.css','/alerts.js','/trends.js','/access-ar.js'}
  apis={'/api/health','/api/equipment','/api/telemetry','/api/trends','/api/passport','/api/history'}
  if self.command=='POST':
   if not path.startswith('/api/field/') and path not in {'/api/ar-frame','/api/qr','/api/analyze'}:return False
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=12000000:self.send({'error':'Недопустимый размер кадра'},status=413);return True
   body=self.rfile.read(size)
  else:
   if path not in pages|apis and not path.startswith('/api/field/') and not re.fullmatch(r'/api/(jobs/[a-fA-F0-9]+|document/\d+)|/results/[a-fA-F0-9]+/[\w.-]+|/assets/[\w.-]+',path):return False
   body=None
  base=(PRIVATE/'gpu-url.txt').read_text(encoding='utf-8-sig').strip()
  if urlparse(base).port!=8769:
   if body is not None:self.send({'error':'RTX-сайт не настроен'},status=503);return True
   return False
  req=urllib.request.Request(base+('/mobile.html' if self.path=='/' else self.path),data=body,headers={'X-Forwarded-Proto':'https',**{k:self.headers[k] for k in ('Accept','Content-Type','X-Captured-At','Cookie','X-Field-Request') if k in self.headers}})
  try:
   with mobile_http.open(req,timeout=90 if body else 10) as res:self.send(res.read(),res.headers.get('Content-Type','application/octet-stream'),res.status,res.headers)
  except urllib.error.HTTPError as exc:self.send(exc.read(),exc.headers.get('Content-Type','application/json'),exc.code,exc.headers)
  except OSError:self.send({'error':'Нет связи с RTX через Radmin'},status=503)
  return True
 def do_GET(self):
  try:self.get()
  except Exception as e:self.send({'error':str(e)},status=500)
 def get(self):
  if self.rtx_mobile():return
  u=urlparse(self.path);path=unquote(u.path);q=parse_qs(u.query)
  if path=='/api/health':return self.send({'ok':True,'deployment':'hack102-lan','gpu':gpu_client.health()})
  if path.startswith('/api/') and not self.auth():return self.send({'error':'Откройте мобильную страницу по QR подключения или введите код доступа.'},status=401)
  if path=='/api/equipment':
   with db() as c:return self.send(c.execute('SELECT tag,name,serial_no FROM equipment ORDER BY tag').fetchall())
  if path=='/api/passport':
   p=passport(q.get('tag',[''])[0]);return self.send(p or {'error':'Насос не найден'},status=200 if p else 404)
  if path=='/api/trends':return self.send(demo_trends.history(db,q.get('tag',[''])[0],q.get('demo',['0'])[0]=='1'))
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
  if self.rtx_mobile():return
  try:
   if not self.auth():return self.send({'error':'Нужен код доступа'},status=401)
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=12_000_000:return self.send({'error':'Файл должен быть меньше 12 МБ'},status=413)
   body=self.rfile.read(size);u=urlparse(self.path);q=parse_qs(u.query)
   if u.path=='/api/ar-frame':
    try:
     accept='application/json' if 'application/json' in self.headers.get('Accept','') else 'image/jpeg'
     result=gpu_client.request('/live',body,Accept=accept)
     return self.send(result,'application/json' if result.startswith(b'{') else 'image/jpeg')
    except urllib.error.HTTPError as exc:return self.send({'error':'GPU занят' if exc.code==429 else 'Ошибка службы GPU: '+str(exc.code)},status=exc.code)
    except OSError:return self.send({'error':'GPU недоступен. Запустите службу на ноутбуке.'},status=503)
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
 threading.Thread(target=demo_trends.writer,args=(db,),daemon=True).start()
 http=ThreadingHTTPServer(('0.0.0.0',8769),Handler)
 threading.Thread(target=http.serve_forever,daemon=True).start()
 https=ThreadingHTTPServer(('0.0.0.0',8443),Handler);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(PRIVATE/'server.pem',PRIVATE/'server-key.pem');https.socket=ctx.wrap_socket(https.socket,server_side=True)
 print('HTTP :8769 / HTTPS :8443',flush=True);https.serve_forever()
if __name__=='__main__':main()
