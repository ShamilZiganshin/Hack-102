"""Long-lived local inference worker. One JSON line in, one JSON line out."""
from pathlib import Path
import sys,json,time,contextlib
ROOT=Path(__file__).resolve().parent
key=sys.argv[1]
with contextlib.redirect_stdout(sys.stderr):
 import numpy as np
 from PIL import Image
 if key=='rust':
  sys.path.insert(0,str(ROOT.parent/'детекция ржавчины'))
  from rust_model import RustSegmenter
  model=RustSegmenter()
 else:
  sys.path.insert(0,str(ROOT.parent/'детекция масла'))
  from surface_model import SurfaceOilModel
  model=SurfaceOilModel(hybrid=True)
print(json.dumps({'ready':key}),flush=True)
for line in sys.stdin:
 try:
  req=json.loads(line);t=time.perf_counter()
  with contextlib.redirect_stdout(sys.stderr):
   rgb=np.array(Image.open(req['image']).convert('RGB'))
   p=model.predict(rgb,req.get('mode','fast256')) if key=='rust' else model.predict(rgb)['dense_score']
   mask=p>=.5
   Image.fromarray(mask.astype('uint8')*255).save(req['mask'])
  print(json.dumps({'key':key,'seconds':round(time.perf_counter()-t,3),'percent':round(float(mask.mean()*100),3)}),flush=True)
 except Exception as e: print(json.dumps({'error':str(e)}),flush=True)
