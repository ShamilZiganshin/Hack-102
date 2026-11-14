from pathlib import Path
import os,time,json
os.environ['DO_NOT_TRACK']='1'
import openvino as ov,cv2,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
LABELS=['gas-pipelines','deformation','corrosion','coating degradation','deformations']
def run(image,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);core=ov.Core();model=core.read_model(ROOT/'models/specialists/pipeline.xml')
 print('ports',[(v.any_name,list(v.partial_shape)) for v in model.inputs],[(v.any_name,str(v.partial_shape)) for v in model.outputs],flush=True)
 start=time.perf_counter();compiled=core.compile_model(model,'CPU',{'INFERENCE_NUM_THREADS':4,'PERFORMANCE_HINT':'LATENCY'});load=time.perf_counter()-start
 bgr=cv2.imdecode(np.fromfile(image,np.uint8),cv2.IMREAD_COLOR);h,w=bgr.shape[:2];scale=min(640/w,640/h);nw,nh=round(w*scale),round(h*scale);left=(640-nw)//2;top=(640-nh)//2
 padded=np.full((640,640,3),114,np.uint8);padded[top:top+nh,left:left+nw]=cv2.resize(bgr,(nw,nh));x=padded[:,:,::-1].transpose(2,0,1)[None].astype(np.float32)
 start=time.perf_counter();raw=compiled(x);elapsed=time.perf_counter()-start
 arr={o.any_name:np.array(v) for o,v in raw.items()};np.savez(out/'raw_outputs.npz',**arr);print('outputs',[(k,v.shape,v.reshape(-1)[:12].tolist()) for k,v in arr.items()],flush=True)
 boxes=next(v for k,v in arr.items() if k=='boxes').reshape(-1,5);labels=next(v for k,v in arr.items() if k=='labels').reshape(-1)
 records=[];over=bgr.copy()
 for box,cls in zip(boxes,labels):
  cls=int(cls);score=float(box[4])
  if cls<0 or cls>=len(LABELS) or score<.05:continue
  xy=[max(0,min(w,float((box[0]-left)/scale))),max(0,min(h,float((box[1]-top)/scale))),max(0,min(w,float((box[2]-left)/scale))),max(0,min(h,float((box[3]-top)/scale)))]
  records.append({'class':LABELS[cls],'class_id':cls,'confidence':score,'box':xy,'above_default':score>=.25})
  if score>=.25:
   a,b,c,d=map(round,xy);cv2.rectangle(over,(a,b),(c,d),(60,130,255),2);cv2.putText(over,f'{LABELS[cls]} {score:.2f}',(a,max(15,b-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,(60,130,255),1,cv2.LINE_AA)
 Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).save(out/'original.jpg',quality=95);Image.fromarray(cv2.cvtColor(over,cv2.COLOR_BGR2RGB)).save(out/'overlay.jpg',quality=95)
 report={'key':'pipeline','model':'Intel YOLOX-L pipeline defect','task':'detect','size':[w,h],'seconds':elapsed,'load_seconds':load,'default_threshold':.25,'stored_minimum_threshold':.05,'detections':records,'preprocessing':'centered letterbox 640, pad114, RGB, FP32 0..255 NCHW','classes':LABELS}
 (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
 if a.image:print(json.dumps(run(a.image,a.out),ensure_ascii=False))
 else:
  rows=[]
  for i in ['01','02','03']:
   try:
    r=run(ROOT/'samples'/f'{i}.jpg',ROOT/'outputs/specialists/pipeline'/i);rows.append(dict(sample=i,**r));print('pipeline',i,'seconds',round(r['seconds'],3),'detections',[(v['class'],round(v['confidence'],3)) for v in r['detections']],flush=True)
   except Exception as e:print('ERROR',i,repr(e),flush=True);rows.append({'sample':i,'error':str(e)})
  (ROOT/'outputs/specialists/pipeline_comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
