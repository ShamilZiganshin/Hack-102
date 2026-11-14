from pathlib import Path
import os,json,time
ROOT=Path(__file__).resolve().parent
os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
import torch,numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont,ImageOps
from transformers import CLIPSegProcessor,CLIPSegForImageSegmentation
PROMPTS=['oil stains on machinery','wet oily metal surface','black greasy oil residue','dry metal surface','rust on metal','shadow']
if __name__=='__main__':
 torch.set_num_threads(4)
 model=CLIPSegForImageSegmentation.from_pretrained(ROOT/'models/clipseg',local_files_only=True,use_safetensors=True).eval()
 processor=CLIPSegProcessor.from_pretrained(ROOT/'models/clipseg',local_files_only=True)
 out=ROOT/'regression/clipseg';out.mkdir(exist_ok=True)
 names=[ROOT/'regression/reported_photo.jpg',ROOT/'samples/vehicle_pump.jpg',ROOT/'samples/tractor_pump.jpg',ROOT/'samples/excavator_pump.jpg']
 records=[]
 for path in names:
  im=Image.open(path).convert('RGB');im.thumbnail((1600,1600));rgb=np.array(im);t=time.perf_counter()
  inputs=processor(text=PROMPTS,images=[im]*len(PROMPTS),padding=True,return_tensors='pt')
  with torch.inference_mode():logits=model(**inputs).logits
  probs=logits.sigmoid().numpy();maps=np.stack([cv2.resize(p,im.size,interpolation=cv2.INTER_LINEAR) for p in probs]);np.save(out/f'{path.stem}_maps.npy',maps)
  record={'image':path.name,'prompts':PROMPTS,'seconds':time.perf_counter()-t,'stats':[{'prompt':p,'max':float(m.max()),'mean':float(m.mean()),'area_above_0_5':float((m>=.5).mean())} for p,m in zip(PROMPTS,maps)]};records.append(record);print(record,flush=True)
  w,h=400,400;canvas=Image.new('RGB',(w*3,2*(h+42)),(17,23,27));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
  for k,(prompt,m) in enumerate(zip(PROMPTS,maps)):
   blend=rgb.copy();mask=m>=.5;blend[mask]=(blend[mask]*.5+np.array([32,210,186])*.5).astype(np.uint8)
   image=ImageOps.contain(Image.fromarray(blend),(w,h));x=(k%3)*w;y=(k//3)*(h+42);canvas.paste(image,(x+(w-image.width)//2,y+(h-image.height)//2));draw.text((x+10,y+h+8),prompt,font=font,fill='white')
  canvas.save(out/f'{path.stem}_prompts.jpg',quality=94)
 (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
