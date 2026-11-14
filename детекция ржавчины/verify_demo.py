from pathlib import Path
import json,time,hashlib,requests
import numpy as np
from PIL import Image
from rust_model import *
r=ROOT
s=requests.Session();s.trust_env=False
checks={}
for path in ['/api/health','/api/examples','/api/benchmark','/']:
    response=s.get('http://127.0.0.1:8765'+path,timeout=20);response.raise_for_status();checks[path]=response.status_code
with (r/'samples/flickr_author_example.jpg').open('rb') as f:
    start=time.perf_counter();response=s.post('http://127.0.0.1:8765/api/analyze',files={'image':('flickr_author_example.jpg',f,'image/jpeg')},data={'mode':'quality'},timeout=120);response.raise_for_status();result=response.json();print('UPLOAD RESULT',result,flush=True)
checks['upload']={'status':response.status_code,'run':result['run'],'request_seconds':time.perf_counter()-start}
for kind in ['mask','overlay']:
    response=s.get(f"http://127.0.0.1:8765/api/export/{result['run']}/{kind}?threshold=.61",timeout=20);response.raise_for_status()
    import io
    im=Image.open(io.BytesIO(response.content));assert im.size==(result['width'],result['height']);checks['export_'+kind]={'status':response.status_code,'size':im.size,'format':im.format}
response=s.post('http://127.0.0.1:8765/api/analyze',files={'image':('bad.jpg',b'not an image','image/jpeg')},timeout=20);assert response.status_code==400;checks['invalid_image']=response.status_code
(r/'outputs/smoke_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
# Save exact float maps for exports from the precomputed test examples.
model=RustSegmenter()
for path in sorted((DATA/'test/images').glob('*.jpg')):
    p=model.predict(np.asarray(Image.open(path).convert('RGB')),'quality');np.save(r/'outputs'/path.stem/'probability.npy',p)
    print('Exact probability saved',path.name,flush=True)
manifest={}
for name in ['models/ostrava_original.pth','models/ostrava_unetpp_resnet50.safetensors','research/ostrava_dataset.zip','repositories/ostrava.zip','repositories/spotrust.zip']:
    p=r/name;h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    manifest[name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
(r/'research/integrity.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('CHECKS COMPLETE',checks,flush=True)
