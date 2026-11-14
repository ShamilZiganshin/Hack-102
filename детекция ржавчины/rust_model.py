from pathlib import Path
import os,time,json
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TORCH_HOME',str(Path(__file__).parent/'.cache/torch'))
import cv2,numpy as np,torch
import segmentation_models_pytorch as smp
from safetensors.torch import load_file
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/corrosion-in-industrial-complexes-in-ostrava'
torch.set_num_threads(4)
class RustSegmenter:
    def __init__(self):
        sd=load_file(str(ROOT/'models/ostrava_unetpp_resnet50.safetensors'))
        self.model=smp.UnetPlusPlus(encoder_name='resnet50',encoder_weights=None,classes=1)
        self.model.load_state_dict({k[6:]:v for k,v in sd.items() if k.startswith('model.')},strict=True)
        self.model.eval();self.mean=sd['mean'];self.std=sd['std']
    @torch.inference_mode()
    def raw(self,rgb,size=256,flip=False):
        a=cv2.resize(rgb,(size,size),interpolation=cv2.INTER_NEAREST)
        x=torch.from_numpy(a.transpose(2,0,1).copy()).float()[None]
        # Deliberately retain 0..255: this checkpoint was TRAINED with ToTensorV2
        # on uint8 arrays and (image - ImageNet mean) / ImageNet std, without /255.
        x=(x-self.mean)/self.std
        if flip:x=torch.flip(x,[-1])
        p=self.model(x).sigmoid()
        if flip:p=torch.flip(p,[-1])
        return p[0,0].numpy()
    def predict(self,rgb,mode='quality'):
        config=json.loads((ROOT/'config.json').read_text()) if (ROOT/'config.json').exists() else {}
        mode=config.get('quality_mode','tta256') if mode=='quality' else mode
        sizes=[256,384] if mode=='multiscale' else [384] if mode=='detail384' else [512] if mode=='detail512' else [256]
        maps=[]
        for size in sizes:
            for flip in ([False,True] if mode in ('tta256','multiscale') else [False]):
                p=self.raw(rgb,size,flip)
                maps.append(cv2.resize(p,(rgb.shape[1],rgb.shape[0]),interpolation=cv2.INTER_LINEAR))
        return np.mean(maps,axis=0).astype(np.float32)
def guided(rgb,p,radius=12,eps=.01):
    guide=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY).astype(np.float32)/255
    k=(radius*2+1,)*2
    box=lambda x:cv2.boxFilter(x,-1,k,normalize=True,borderType=cv2.BORDER_REFLECT)
    mi,mp=box(guide),box(p); var=box(guide*guide)-mi*mi
    a=(box(guide*p)-mi*mp)/(var+eps);b=mp-a*mi
    return np.clip(box(a)*guide+box(b),0,1)
def metrics(p,gt,threshold=.5):
    pred=p>=threshold;gt=gt.astype(bool)
    tp=int(np.logical_and(pred,gt).sum());fp=int(np.logical_and(pred,~gt).sum());fn=int(np.logical_and(~pred,gt).sum())
    return dict(iou=tp/max(tp+fp+fn,1),dice=2*tp/max(2*tp+fp+fn,1),precision=tp/max(tp+fp,1),recall=tp/max(tp+fn,1),tp=tp,fp=fp,fn=fn)
def overlay(rgb,mask,alpha=.42):
    out=rgb.copy();out[mask]=np.round(rgb[mask]*(1-alpha)+np.array([255,91,45])*alpha).astype(np.uint8)
    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out,contours,-1,(255,171,92),max(1,round(max(rgb.shape[:2])/1200)))
    return out
def save_result(rgb,p,out,threshold=.5,meta=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);mask=p>=threshold
    Image.fromarray(rgb).save(out/'original.jpg',quality=94)
    Image.fromarray(overlay(rgb,mask)).save(out/'overlay.jpg',quality=95)
    Image.fromarray(mask.astype(np.uint8)*255).save(out/'mask.png')
    Image.fromarray(np.round(np.clip(p,0,1)*255).astype(np.uint8)).save(out/'probability.png')
    heat=cv2.cvtColor(cv2.applyColorMap(np.uint8(p*255),cv2.COLORMAP_INFERNO),cv2.COLOR_BGR2RGB)
    Image.fromarray(heat).save(out/'heatmap.jpg',quality=92)
    result={'threshold':threshold,'rust_percent_of_image':round(float(mask.mean()*100),3),'width':rgb.shape[1],'height':rgb.shape[0],**(meta or {})}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
