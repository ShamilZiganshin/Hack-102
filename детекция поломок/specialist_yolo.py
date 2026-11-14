from pathlib import Path
import os,time,json
import numpy as np,cv2,torch
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
os.environ['YOLO_CONFIG_DIR']=str(ROOT/'.cache/ultralytics')
from ultralytics import YOLO
MODELS={'crack_n':'crack_yolov8n.pt','crack_m':'crack_yolov8m.pt','industrial':'industrial_crack.pt'}
LABELS={'crack_n':'OpenSistemas YOLOv8n-seg','crack_m':'OpenSistemas YOLOv8m-seg','industrial':'hyunon industrial crack'}
def run(key,image,out,imgsz=960):
 torch.set_num_threads(4)
 out=Path(out);out.mkdir(parents=True,exist_ok=True);bgr=cv2.imdecode(np.fromfile(image,np.uint8),cv2.IMREAD_COLOR);h,w=bgr.shape[:2]
 start=time.perf_counter();model=YOLO(ROOT/'models/specialists'/MODELS[key]);load=time.perf_counter()-start
 start=time.perf_counter();result=model.predict(bgr,imgsz=imgsz,conf=.05,iou=.5,device='cpu',retina_masks=True,verbose=False)[0];elapsed=time.perf_counter()-start
 records=[];maskall=np.zeros((h,w),np.uint8);over=bgr.copy()
 for i,box in enumerate(result.boxes):
  conf=float(box.conf[0]);cls=int(box.cls[0]);xy=box.xyxy[0].cpu().numpy().tolist();name=result.names[cls]
  record={'class':name,'class_id':cls,'confidence':conf,'box':xy,'above_default':conf>=.25}
  if result.masks is not None and i<len(result.masks.data):
   mask=result.masks.data[i].cpu().numpy();mask=cv2.resize(mask,(w,h),interpolation=cv2.INTER_NEAREST)>.5
   Image.fromarray(mask.astype(np.uint8)*255).save(out/f'mask_{i}.png')
   if conf>=.25:maskall[mask]=255
  records.append(record)
 if maskall.any():over[maskall>0]=(over[maskall>0]*.55+np.array([45,91,255])*.45).astype(np.uint8)
 for record in records:
  if record['confidence']<.25:continue
  a,b,c,d=map(round,record['box']);cv2.rectangle(over,(a,b),(c,d),(70,150,255),2);cv2.putText(over,f"{record['class']} {record['confidence']:.2f}",(a,max(15,b-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,(70,150,255),1,cv2.LINE_AA)
 Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).save(out/'original.jpg',quality=95);Image.fromarray(cv2.cvtColor(over,cv2.COLOR_BGR2RGB)).save(out/'overlay.jpg',quality=95);Image.fromarray(maskall).save(out/'mask.png')
 report={'model':LABELS[key],'key':key,'task':model.task,'classes':result.names,'size':[w,h],'imgsz':imgsz,'seconds':elapsed,'load_seconds':load,'default_threshold':.25,'stored_minimum_threshold':.05,'detections':records,'mask_percent_of_image':float((maskall>0).mean()*100),'model_yaml':str(model.model.yaml.get('yaml_file'))}
 (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--model',choices=list(MODELS));p.add_argument('--image',type=Path);p.add_argument('--out',type=Path);p.add_argument('--size',type=int,default=960);args=p.parse_args()
 if args.model:print(json.dumps(run(args.model,args.image,args.out,args.size),ensure_ascii=False))
 else:
  rows=[]
  for key in MODELS:
   for i in ['01','02','03']:
    try:
     row=run(key,ROOT/'samples'/f'{i}.jpg',ROOT/'outputs/specialists'/key/i);rows.append(dict(sample=i,**row));print(key,i,'seconds',round(row['seconds'],2),'detections',[(v['class'],round(v['confidence'],3)) for v in row['detections']],flush=True)
    except Exception as e:print('ERROR',key,i,repr(e),flush=True);rows.append({'key':key,'sample':i,'error':str(e)})
  (ROOT/'outputs/specialists/yolo_comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
