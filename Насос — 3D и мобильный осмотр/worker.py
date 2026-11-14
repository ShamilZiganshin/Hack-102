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
 elif key=='crack':
  import os
  from ultralytics import YOLO
  model=YOLO(ROOT.parent/'детекция поломок/models/specialists/crack_yolov8n.pt')
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
   if key=='crack':
    prediction=model.predict(rgb[:,:,::-1].copy(),imgsz=640,conf=.25,retina_masks=True,verbose=False,device=os.environ.get('PUMP_DEVICE','cpu'))[0]
    mask=(prediction.masks.data.amax(0).cpu().numpy()>.5 if prediction.masks is not None else np.zeros(rgb.shape[:2],dtype=bool))
    confidence=float(prediction.boxes.conf.max().item()) if mask.any() else None
   else:
    p=model.predict(rgb,req.get('mode','fast256')) if key=='rust' else model.predict(rgb,imgsz=640 if req.get('mode')=='preview' else 960)['dense_score']
    mask=p>=.5
    confidence=float(p[mask].mean()) if mask.any() else None
   Image.fromarray(mask.astype('uint8')*255).save(req['mask'])
  print(json.dumps({'key':key,'confidence':round(100*confidence,1) if confidence is not None else None,'seconds':round(time.perf_counter()-t,3),'percent':round(float(mask.mean()*100),3)}),flush=True)
 except Exception as e: print(json.dumps({'error':str(e)}),flush=True)
