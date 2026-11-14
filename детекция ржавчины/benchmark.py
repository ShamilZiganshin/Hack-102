from pathlib import Path
import json,time,zipfile
import numpy as np,cv2
from PIL import Image
from rust_model import *
if __name__=='__main__':
    model=RustSegmenter();reports={}
    modes=['fast','tta256','detail384','detail512','multiscale']
    for split in ['validation','test']:
        if split=='test':
            ranked=sorted(reports['validation'].items(),key=lambda kv:kv[1]['mean_iou'],reverse=True)
            chosen=ranked[0][0];(ROOT/'config.json').write_text(json.dumps({'quality_mode':chosen,'threshold':.5},indent=2))
            modes=list(dict.fromkeys(['fast',chosen]));print('LOCKED QUALITY MODE',chosen,flush=True)
        reports[split]={};rows={mode:[] for mode in modes}
        for path in sorted((DATA/split/'images').glob('*.jpg')):
            rgb=np.asarray(Image.open(path).convert('RGB'));gt=np.asarray(Image.open(DATA/split/'masks'/f'{path.stem}.png').convert('L'))>0
            # Shared raw forward passes, so mode timing below excludes image I/O.
            raws={};times={}
            for size in sorted(set([256]+([384,512] if split=='validation' else [384] if chosen in ['multiscale','detail384'] else [512] if chosen=='detail512' else []))):
                for flip in ([False,True] if size in [256,384] else [False]):
                    start=time.perf_counter();raws[(size,flip)]=model.raw(rgb,size,flip);times[(size,flip)]=time.perf_counter()-start
            for mode in modes:
                keys={'fast':[(256,False)],'tta256':[(256,False),(256,True)],'detail384':[(384,False)],'detail512':[(512,False)],'multiscale':[(256,False),(256,True),(384,False),(384,True)]}[mode]
                p=np.mean([cv2.resize(raws[k],(rgb.shape[1],rgb.shape[0]),interpolation=cv2.INTER_LINEAR) for k in keys],axis=0)
                m=metrics(p,gt);m.update(image=path.name,seconds=sum(times[k] for k in keys))
                if mode=='fast':
                    gt256=cv2.resize(gt.astype(np.uint8),(256,256),interpolation=cv2.INTER_NEAREST)>0
                    m['author_resolution']=metrics(raws[(256,False)],gt256)
                rows[mode].append(m)
                if split=='test' and mode==chosen:
                    save_result(rgb,p,ROOT/'outputs'/path.stem,meta={'image':path.name,'mode':mode,'seconds':m['seconds'],'metrics':{k:m[k] for k in ['iou','dice','precision','recall']},'source':'Ostrava test split (not an independent external dataset)'})
            print(split,path.name,{mode:round(rows[mode][-1]['iou'],4) for mode in modes},flush=True)
        for mode,row in rows.items():
            totals={k:sum(x[k] for x in row) for k in ['tp','fp','fn']};tp,fp,fn=(totals[k] for k in ['tp','fp','fn'])
            reports[split][mode]={'count':len(row),'mean_iou':float(np.mean([x['iou'] for x in row])),'mean_dice':float(np.mean([x['dice'] for x in row])),'dataset_iou':tp/(tp+fp+fn),'mean_seconds':float(np.mean([x['seconds'] for x in row])),'images':row}
        (ROOT/'outputs/benchmark.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
        print('SUMMARY',split,{k:{m:round(v[m],4) for m in ['mean_iou','mean_dice','mean_seconds']} for k,v in reports[split].items()},flush=True)
