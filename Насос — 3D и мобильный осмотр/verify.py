from pathlib import Path
import sys,json,time,urllib.request,urllib.error,ssl,hashlib
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import psycopg
from PIL import Image
import zxingcpp
cfg=json.loads((ROOT/'private/config.json').read_text(encoding='utf-8'));base='http://127.0.0.1:8769';op=urllib.request.build_opener(urllib.request.ProxyHandler({}));checks=[]
def call(path,body=None,headers=None):
 return op.open(urllib.request.Request(base+path,data=body,headers={'X-Access-Key':cfg['access_key'],**(headers or {})}),timeout=20)
def get(path):return json.load(call(path))
def check(name,x):
 assert x,name
 checks.append(name);print('PASS',name,flush=True)
def main():
 check('Server has both warm models',all(v['ready'] for v in get('/api/health')['models'].values()))
 equipment=get('/api/equipment');check('Four real assets',len(equipment)==4)
 for i in range(1,5):
  tag=f'AMS-PS-00{i}';p=get('/api/passport?tag='+tag)
  check(tag+' has 34 sourced passport values',len(p['passport_parameters'])==34 and all(x['document_id'] and x['page'] for x in p['passport_parameters']))
  check(tag+' no invented approved limits',not p['limits'])
  real=get('/api/telemetry?tag='+tag);check(tag+' has no invented actual measurements',all(x['value'] is None for x in real['metrics']))
  demo=get('/api/telemetry?tag='+tag+'&demo=1');states=[m['state'] for m in demo['metrics'] if m['metric']!='operating_hours']
  check(tag+' demo limits read from DB',all(x['limit']['status']=='demo' for x in demo['metrics'] if x['metric']!='operating_hours'))
  check(tag+' expected normal/abnormal',all(s=='within' for s in states) if i==1 else 'outside' in states)
  qr=ROOT/'public/assets'/f'qr-{tag}.png';decoded=zxingcpp.read_barcode(Image.open(qr));check(tag+' QR contents',decoded.text=='KIBER102:'+tag)
  decoded_api=json.load(call('/api/qr',qr.read_bytes()));check(tag+' camera decode endpoint',decoded_api['tag']==tag)
 first=get('/api/telemetry?tag=AMS-PS-001&demo=1');time.sleep(2);second=get('/api/telemetry?tag=AMS-PS-001&demo=1');check('Demo values change on server',first['metrics']!=second['metrics'])
 try:op.open(base+'/api/passport?tag=AMS-PS-001');raise AssertionError('unauthenticated request allowed')
 except urllib.error.HTTPError as e:check('Passport requires access key',e.code==401)
 try:call('/api/analyze?tag=AMS-PS-001',b'not an image');raise AssertionError('bad image accepted')
 except urllib.error.HTTPError as e:check('Invalid images rejected',e.code==400)
 check('Private config not served',op.open(base+'/').status==200)
 for path in ['/private/config.json','/../private/config.json']:
  try:op.open(base+path);raise AssertionError('private file exposed')
  except urllib.error.HTTPError as e:check('Private files isolated '+path,e.code==404)
 ctx=ssl.create_default_context(cafile=str(ROOT/'private/ca.pem'));https=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx));check('HTTPS chain and localhost SAN valid',json.load(https.open('https://127.0.0.1:8443/api/health'))['ok'])
 doc=p['passport_document_id'];content=call('/api/document/'+str(doc)).read()
 with psycopg.connect(cfg['database']) as c:sha=c.execute('SELECT sha256 FROM documents WHERE id=%s',(doc,)).fetchone()[0]
 check('Passport PDF exported byte-exact',hashlib.sha256(content).hexdigest()==sha)
 # Real inference on a real provided casing photograph, through all three server integrations.
 photo=ROOT.parent/'детекция поломок/samples/reported_casing.jpg'
 job=json.load(call('/api/analyze?tag=AMS-PS-004&cracks=1',photo.read_bytes()))
 (ROOT/'outputs/verification-job.json').write_text(json.dumps(job),encoding='utf-8')
 print('Inference job',job['id'],flush=True)
 start=time.time()
 while time.time()-start<1500:
  r=get('/api/jobs/'+job['id'])
  if r['status'] in ('done','error'):break
  time.sleep(2)
 check('All-three inference finished',r['status']=='done')
 check('All three actual model outputs',len(r['models'])==3 and all('error' not in x for x in r['models']))
 check('Hybrid crack verifier used',next(x for x in r['models'] if x['key']=='crack')['verification']['version']=='hybrid-review-v2')
 check('Result written to PostgreSQL history',any(h['frame_id']==job['id'] for h in get('/api/history?tag=AMS-PS-004')))
 check('Rendered result downloadable',call(r['overlay']).headers['Content-Type']=='image/jpeg')
 (ROOT/'outputs/verification.json').write_text(json.dumps({'checks':checks,'job':r},ensure_ascii=False,indent=2),encoding='utf-8')
 print('ALL CHECKS PASSED',len(checks),flush=True)
if __name__=='__main__':
 try:main()
 finally:(ROOT/'outputs/checks-progress.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
