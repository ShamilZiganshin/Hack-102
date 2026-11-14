"""Automatic local oil-like stain instance segmentation. No manual prompts."""
from pathlib import Path
import os,json,time
ROOT=Path(__file__).resolve().parent
for key,value in {'YOLO_CONFIG_DIR':str(ROOT/'.runtime/ultralytics'),'YOLO_OFFLINE':'true','YOLO_AUTOINSTALL':'false','MPLCONFIGDIR':str(ROOT/'.runtime/matplotlib')}.items():os.environ[key]=value
import numpy as np,torch,yaml,cv2
from PIL import Image,ImageOps
from safetensors.torch import load_file
from ultralytics import YOLO
from ultralytics.utils import SETTINGS
SETTINGS.update({'sync':False})
torch.set_num_threads(4)
DEFAULT_THRESHOLD=.8
class OilDetector:
 def __init__(self,variant='nano'):
  if variant not in ['nano','medium']:raise ValueError('Unknown model')
  self.variant=variant;self.name='spill_leak_nano' if variant=='nano' else 'spill_leak'
  meta=json.loads((ROOT/'models'/f'{self.name}.json').read_text(encoding='utf-8'))
  path=ROOT/'models'/meta['architecture']['yaml_file'];path.write_text(yaml.safe_dump(meta['architecture'],allow_unicode=True),encoding='utf-8')
  self.yolo=YOLO(str(path),task='segment',verbose=False)
  self.yolo.model.load_state_dict(load_file(str(ROOT/'models'/f'{self.name}.safetensors')),strict=True)
  self.yolo.model.names={int(k):v for k,v in meta['names'].items()}
 def predict(self,rgb,imgsz=960):
  t=time.perf_counter()
  result=self.yolo.predict(source=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),conf=.05,imgsz=imgsz,device=os.environ.get('PUMP_DEVICE','cpu'),verbose=False,retina_masks=True,save=False,max_det=40)[0]
  masks=[];detections=[]
  if result.masks is not None:
   for index,(box,mask) in enumerate(zip(result.boxes,result.masks.data.cpu().numpy())):
    masks.append(mask>.5);detections.append({'id':index,'class':self.yolo.names[int(box.cls[0])],'confidence':float(box.conf[0]),'bbox_xyxy':[float(v) for v in box.xyxy[0]]})
  return {'instances':masks,'detections':detections,'seconds':round(time.perf_counter()-t,4),'model':self.variant,'imgsz':imgsz}
def combined_mask(result,shape,threshold):
 masks=[m for m,d in zip(result['instances'],result['detections']) if d['confidence']>=threshold]
 return np.logical_or.reduce(masks) if masks else np.zeros(shape,dtype=bool)
def overlay(rgb,mask,alpha=.45):
 out=rgb.copy();out[mask]=(out[mask]*(1-alpha)+np.array([32,210,186])*alpha).astype(np.uint8)
 contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
 cv2.drawContours(out,contours,-1,(100,255,224),max(1,round(rgb.shape[1]/1200)))
 return out
def save_prediction(rgb,result,out,extra=None,threshold=DEFAULT_THRESHOLD):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 mask=combined_mask(result,rgb.shape[:2],threshold);scoremap=np.zeros(rgb.shape[:2],np.float32)
 for m,d in zip(result['instances'],result['detections']):scoremap[m]=np.maximum(scoremap[m],d['confidence'])
 Image.fromarray(rgb).save(out/'original.jpg',quality=95)
 Image.fromarray(overlay(rgb,mask)).save(out/'overlay.jpg',quality=95)
 Image.fromarray(mask.astype(np.uint8)*255).save(out/'mask.png')
 Image.fromarray(np.round(scoremap*255).astype(np.uint8)).save(out/'scoremap.png')
 arr=np.stack(result['instances']) if result['instances'] else np.empty((0,*rgb.shape[:2]),bool)
 np.savez_compressed(out/'instances.npz',bits=np.packbits(arr,axis=2),height=rgb.shape[0],width=rgb.shape[1])
 selected=[d for d in result['detections'] if d['confidence']>=threshold]
 metadata={k:v for k,v in result.items() if k!='instances'}
 metadata.update({'confidence_threshold':threshold,'count':len(selected),'mask_percent_of_image':round(float(mask.mean()*100),4),'width':rgb.shape[1],'height':rgb.shape[0],'status':'suspected_oil' if selected else 'no_detection','note':'Следы, похожие на масло; состав жидкости и активность утечки по одному фото не подтверждаются.',**(extra or {})})
 (out/'result.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8');return metadata
def load_result_mask(out,threshold):
 out=Path(out);meta=json.loads((out/'result.json').read_text(encoding='utf-8'))
 with np.load(out/'instances.npz') as z:
  masks=np.unpackbits(z['bits'],axis=2,count=int(z['width'])).astype(bool)
 chosen=[m for m,d in zip(masks,meta['detections']) if d['confidence']>=threshold]
 return (np.logical_or.reduce(chosen) if chosen else np.zeros((meta['height'],meta['width']),bool)),meta
