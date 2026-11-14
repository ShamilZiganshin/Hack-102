from pathlib import Path
import os,time,json
import numpy as np,torch,cv2
from PIL import Image
ROOT=Path(__file__).resolve().parent
os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
PROMPTS=['oil stains on machinery','wet oily metal surface','black greasy oil residue']
class SurfaceOilModel:
 def __init__(self,hybrid=False):
  from transformers import CLIPSegProcessor,CLIPSegForImageSegmentation
  self.hybrid=hybrid;torch.set_num_threads(4)
  self.model=CLIPSegForImageSegmentation.from_pretrained(ROOT/'models/clipseg',local_files_only=True,use_safetensors=True).eval()
  self.processor=CLIPSegProcessor.from_pretrained(ROOT/'models/clipseg',local_files_only=True,use_fast=False)
  self.detector=None
  if hybrid:
   from oil_model import OilDetector
   self.detector=OilDetector('nano')
 @torch.inference_mode()
 def predict(self,rgb,imgsz=960):
  start=time.perf_counter();im=Image.fromarray(rgb)
  x=self.processor(text=PROMPTS,images=[im]*len(PROMPTS),return_tensors='pt',padding=True)
  maps=self.model(**x).logits.sigmoid().cpu().numpy()
  semantic=cv2.resize(maps.max(axis=0),(rgb.shape[1],rgb.shape[0]),interpolation=cv2.INTER_LINEAR).astype(np.float32)
  score=semantic.copy();expert=[]
  if self.detector is not None:
   y=self.detector.predict(rgb,imgsz=960)
   for mask,d in zip(y['instances'],y['detections']):
    if d['confidence']>=.8:score[mask]=np.maximum(score[mask],d['confidence']);expert.append(d)
  return {'model':'hybrid' if self.hybrid else 'clipseg','kind':'semantic','dense_score':score,'semantic_score':semantic,'detections':[],'expert_detections':expert,'prompts':PROMPTS,'seconds':round(time.perf_counter()-start,4),'imgsz':352,'confidence_threshold':.5,'fusion':'pixelwise maximum of CLIPSeg text maps; YOLO26 Nano proposals with confidence >=0.8 are added in hybrid mode','trained_new_weights':False,'warning':'Experimental uncalibrated fusion, not a trained or validated new oil model.'}
def save_surface_prediction(rgb,result,out,extra=None):
 from oil_model import overlay
 out=Path(out);out.mkdir(parents=True,exist_ok=True);score=result['dense_score'];threshold=.5;mask=score>=threshold
 Image.fromarray(rgb).save(out/'original.jpg',quality=95);Image.fromarray(overlay(rgb,mask)).save(out/'overlay.jpg',quality=95);Image.fromarray(mask.astype(np.uint8)*255).save(out/'mask.png');Image.fromarray(np.round(np.clip(score,0,1)*255).astype(np.uint8)).save(out/'scoremap.png');np.save(out/'dense_score.npy',score)
 meta={k:v for k,v in result.items() if k not in ['dense_score','semantic_score']};meta.update(width=rgb.shape[1],height=rgb.shape[0],count=int(mask.any()),mask_percent_of_image=float(mask.mean()*100),status='suspected_surface' if mask.any() else 'no_detection',note='Маска по текстовому описанию; не подтверждает состав жидкости.',**(extra or {}));(out/'result.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');return meta
if __name__=='__main__':
 from PIL import ImageOps
 model=SurfaceOilModel(hybrid=True);sources=json.loads((ROOT/'samples/sources.json').read_text(encoding='utf-8'));sources.append({'id':'reported_photo','file':'../regression/reported_photo.jpg','title':'Контрольное фото пользователя','source':'user-supplied regression image, not a blind test'})
 records=[]
 for it in sources:
  im=ImageOps.exif_transpose(Image.open(ROOT/'samples'/it['file'])).convert('RGB');im.thumbnail((2048,2048));rgb=np.array(im);r=model.predict(rgb)
  for variant in ['clipseg','hybrid']:
   result={**r,'model':variant,'dense_score':r['semantic_score'] if variant=='clipseg' else r['dense_score']};meta=save_surface_prediction(rgb,result,ROOT/'outputs'/f"{variant}_{it['id']}",{'sample_id':it['id'],'title':it['title'],'image':Path(it['file']).name,'source':it['source'],'ground_truth':False});records.append(meta);print(variant,it['id'],round(meta['mask_percent_of_image'],3),meta['seconds'],flush=True)
 (ROOT/'research/v2/surface_comparison.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
