import argparse
import numpy as np
from PIL import Image,ImageOps
from oil_model import OilDetector,save_prediction
if __name__=='__main__':
 parser=argparse.ArgumentParser(description='Offline automatic oil-like stain segmentation')
 parser.add_argument('image');parser.add_argument('--out',required=True);parser.add_argument('--model',choices=['nano','medium'],default='nano');parser.add_argument('--confidence',type=float,default=.8);parser.add_argument('--imgsz',choices=[640,960,1280],type=int,default=960)
 a=parser.parse_args()
 if not .05<=a.confidence<=.99:parser.error('confidence must be between .05 and .99')
 im=ImageOps.exif_transpose(Image.open(a.image)).convert('RGB');im.thumbnail((2048,2048));rgb=np.array(im)
 result=OilDetector(a.model).predict(rgb,a.imgsz);print(save_prediction(rgb,result,a.out,{'image':a.image},threshold=a.confidence))
