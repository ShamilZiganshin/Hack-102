"""Reference-conditioned contour recognition for the three selected views."""
import base64
import io
import threading
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent/'body'
gate = threading.Lock()
model = None

class Inspection:
    def __init__(self):
        self.sift = cv2.SIFT_create(nfeatures=1800)
        self.matcher = cv2.BFMatcher()
        self.refs = []
        with np.load(ROOT/'references.npz') as rows:
            self.weights=rows["weights"]
            for i,name in enumerate(('normal','broken','scene')):
                mask = np.asarray(Image.open(ROOT/(name+'.png')).convert('L'))
                self.refs.append((i,name,mask,rows[name+'_points'],rows[name+'_desc']))

    def predict(self,frame):
        gray = cv2.cvtColor(frame,cv2.COLOR_RGB2GRAY)
        keys,desc = self.sift.detectAndCompute(gray,None)
        if desc is None or len(keys)<12:
            return None,None
        pred = (desc/512. @ self.weights[:-1] + self.weights[-1]).argmax(axis=1)
        best = 0
        winner = mask = None
        for idx,name,template,points,ref in self.refs:
            pairs = self.matcher.knnMatch(ref,desc,k=2)
            good = [a for a,b in pairs if a.distance < .76*b.distance]
            if len(good)<10:continue
            src = np.float32([points[a.queryIdx] for a in good])
            dst = np.float32([keys[a.trainIdx].pt for a in good])
            H,inliers = cv2.findHomography(src,dst,cv2.RANSAC,4)
            if H is None:continue
            chosen = inliers.ravel().astype(bool)
            count = int(chosen.sum())
            if count<10 or count<.42*len(good):continue
            support = cv2.contourArea(cv2.convexHull(src[chosen]))
            if support<.065*np.count_nonzero(template):continue
            votes = np.mean([pred[m.trainIdx]==idx for m,ok in zip(good,chosen) if ok])
            if count*(1+votes)<=best:continue
            candidate = cv2.warpPerspective(template,H,(gray.shape[1],gray.shape[0]),flags=cv2.INTER_NEAREST)
            if np.count_nonzero(candidate)<.014*gray.size:continue
            winner,mask,best = name,candidate,count*(1+votes)
        return winner,mask

def preview_body(handler,body):
    global model
    if not gate.acquire(False):return handler.send({'error':'Предыдущий кадр обрабатывается'},status=429)
    try:
        with Image.open(io.BytesIO(body)) as im:
            if im.width*im.height>24000000:raise ValueError('Слишком большой кадр')
            frame=ImageOps.exif_transpose(im).convert('RGB')
            frame.thumbnail((960,960))
        rgb=np.array(frame)
        if model is None:model=Inspection()
        name,mask=model.predict(rgb)
        if mask is not None:
            contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            color=(255,74,57) if name=='broken' else (41,225,147)
            cv2.drawContours(rgb,contours,-1,color,3,cv2.LINE_AA)
        output=io.BytesIO();Image.fromarray(rgb).save(output,'JPEG',quality=90)
        return handler.send({'image':base64.b64encode(output.getvalue()).decode(),'structure':
            'unknown' if name is None else 'broken' if name=='broken' else 'intact'})
    finally:
        gate.release()


