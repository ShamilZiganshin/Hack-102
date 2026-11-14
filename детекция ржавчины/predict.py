import argparse
from pathlib import Path
from PIL import Image,ImageOps
import numpy as np
from rust_model import RustSegmenter,save_result
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Offline rust segmentation')
    p.add_argument('image',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['quality','fast','detail512'],default='quality');p.add_argument('--threshold',type=float,default=.5)
    args=p.parse_args()
    if not 0<args.threshold<1:p.error('threshold must be between 0 and 1')
    rgb=np.array(ImageOps.exif_transpose(Image.open(args.image)).convert('RGB'))
    prob=RustSegmenter().predict(rgb,args.mode)
    result=save_result(rgb,prob,args.out,args.threshold);np.save(args.out/'probability.npy',prob);print(result)
