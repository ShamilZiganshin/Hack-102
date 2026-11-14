from pathlib import Path
import json,time,io,hashlib,requests,numpy as np
from PIL import Image
from oil_model import ROOT,load_result_mask
s=requests.Session();s.trust_env=False;base='http://127.0.0.1:8766';checks={}
for p in ['/','/api/health','/api/examples','/api/demo/vehicle_pump?model=nano']:
 r=s.get(base+p,timeout=30);r.raise_for_status();checks[p]=r.status_code
with (ROOT/'samples/vehicle_pump.jpg').open('rb') as f:
 r=s.post(base+'/api/analyze',files={'image':('vehicle_pump.jpg',f,'image/jpeg')},data={'model':'nano','imgsz':'960'},timeout=120)
r.raise_for_status();result=r.json();assert any(d['confidence']>=.8 for d in result['detections']);checks['real_upload']={'run':result['run'],'seconds':result['seconds'],'detections':result['count']}
for threshold in [.2,.8,.95]:
 mask,meta=load_result_mask(ROOT/'outputs'/result['run'],threshold)
 r=s.get(f"{base}/api/export/{result['run']}/mask?threshold={threshold}",timeout=20);r.raise_for_status();actual=np.asarray(Image.open(io.BytesIO(r.content)))>0;assert np.array_equal(mask,actual)
 r=s.get(f"{base}/api/export/{result['run']}/json?threshold={threshold}",timeout=20);r.raise_for_status();export=json.loads(r.content);assert export['count']==sum(d['confidence']>=threshold for d in result['detections'])
checks['export_mask_exact']=[.2,.8,.95]
r=s.post(base+'/api/analyze',files={'image':('bad.jpg',b'invalid','image/jpeg')},timeout=20);assert r.status_code==400;checks['invalid_image']=400
r=s.post(base+'/api/analyze',files={'image':('empty.jpg',b'invalid')},data={'model':'unknown'},timeout=20);assert r.status_code==400;checks['invalid_model']=400
r=s.get(base+'/api/export/not_here/mask',timeout=20);assert r.status_code==404;checks['missing_result']=404
# Prove inference does not require network sockets, using locally loaded assets only.
import socket
from oil_model import OilDetector
model=OilDetector('nano');original_socket=socket.socket
def blocked(*args,**kwargs):raise AssertionError('Network access attempted during offline inference')
socket.socket=blocked
try:
 p=model.predict(np.asarray(Image.open(ROOT/'samples/vehicle_pump.jpg').convert('RGB')),640);assert isinstance(p['detections'],list);checks['inference_with_sockets_blocked']='passed'
finally:socket.socket=original_socket
manifest={}
for path in sorted((ROOT/'models').glob('*')):
 if path.is_file():
  h=hashlib.sha256()
  with path.open('rb') as f:
   while chunk:=f.read(1024*1024):h.update(chunk)
  manifest[path.name]={'bytes':path.stat().st_size,'sha256':h.hexdigest()}
(ROOT/'research/integrity.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ROOT/'outputs/API_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2),flush=True)
