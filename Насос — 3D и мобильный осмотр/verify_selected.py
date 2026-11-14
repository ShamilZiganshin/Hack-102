from pathlib import Path
import json,time,urllib.request,sys
ROOT=Path(r'C:\Users\ZiganshinShamil\Desktop\Хакатон 102 v2');P=ROOT/'Насос — 3D и мобильный осмотр';sys.path.insert(0,str(P/'vendor'))
from PIL import Image,ImageOps
import numpy as np
cfg=json.loads((P/'private/config.json').read_text(encoding='utf-8'));op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(path,b=None):return op.open(urllib.request.Request('http://127.0.0.1:8769'+path,data=b,headers={'X-Access-Key':cfg['access_key']}),timeout=30)
chosen=[('rust','AMS-PS-002',ROOT/'детекция ржавчины/data/corrosion-in-industrial-complexes-in-ostrava/test/images/02.jpg',False),('oil','AMS-PS-003',ROOT/'детекция масла/samples/vehicle_pump.jpg',False),('crack','AMS-PS-004',ROOT/'детекция поломок/samples/02.jpg',True)]
reports=[]
if '--rust-only' in sys.argv:
 chosen=chosen[:1];reports=[r for r in json.loads((P/'outputs/photo-selection/selected_results.json').read_text(encoding='utf-8')) if r['key']!='rust']
for key,tag,file,cracks in chosen:
 r=json.load(call('/api/analyze?tag='+tag+'&quality=1&cracks='+str(int(cracks)),file.read_bytes()));id=r['id'];print('Started',key,id,flush=True)
 start=time.time()
 while True:
  r=json.load(call('/api/jobs/'+id))
  if r['status'] in ('done','error'):break
  if time.time()-start>1500:raise TimeoutError(key)
  time.sleep(2)
 assert r['status']=='done',r
 target=next(m for m in r['models'] if m['key']==key);assert 'error' not in target,target
 original=Image.open(P/'outputs'/id/'frame.jpg').convert('RGB');mask=Image.open(P/'outputs'/id/(key+'.png')).convert('L');rgb=np.array(original);m=np.array(mask)>0
 color=np.array({'rust':[255,100,45],'oil':[49,211,225],'crack':[235,65,175]}[key]);rgb[m]=np.round(rgb[m]*.55+color*.45).astype('uint8')
 Image.fromarray(rgb).save(P/'public/assets'/(key+'-selected-overlay.jpg'),quality=95)
 original.save(P/'public/assets'/(key+'-selected-original.jpg'),quality=95)
 reports.append({'key':key,'source':str(file),'job':id,'result':target,'whole_job_seconds':r['seconds']})
 (P/'outputs/photo-selection/selected_results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print('Finished',key,target,flush=True)
print('Selected photos verified',flush=True)
