"""Fit the three demonstration references and a local-feature classifier."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
NAMES = ('normal','broken','scene')

def fit():
    rng = np.random.default_rng(102)
    sift = cv2.SIFT_create(nfeatures=1200)
    features, labels, refs = [], [], {}
    for k,name in enumerate(NAMES):
        gray = np.asarray(Image.open(ROOT/(name+'.jpg')).convert('L'))
        mask = np.asarray(Image.open(ROOT/(name+'.png')).convert('L'))
        h,w = gray.shape
        for i in range(12):
            angle = rng.uniform(-12,12) if i else 0
            scale = rng.uniform(.73,1.05) if i else 1
            mat = cv2.getRotationMatrix2D((w/2,h/2),angle,scale)
            view = cv2.warpAffine(gray,mat,(w,h))
            region = cv2.warpAffine(mask,mat,(w,h),flags=cv2.INTER_NEAREST)
            keys, desc = sift.detectAndCompute(view,region)
            features.append(desc)
            labels.append(np.full(len(desc),k,np.int32))
            if i==0:
                refs[name+'_points'] = np.float32([x.pt for x in keys])
                refs[name+'_desc'] = desc
    # Regularized least squares over normalized local descriptors.
    x=np.vstack(features)/512.
    x=np.column_stack((x,np.ones(len(x),np.float32)))
    y=np.eye(3,dtype=np.float32)[np.concatenate(labels)]
    refs['weights']=np.linalg.solve(x.T@x+2*np.eye(x.shape[1]),x.T@y).astype('float32')
    np.savez_compressed(ROOT/'references.npz',**refs)
    print('Training descriptors',sum(map(len,features)))

if __name__=='__main__':
    fit()
