from pathlib import Path
import cv2
import numpy as np
import openvino as ov
import json

root = Path(__file__).resolve().parent
core = ov.Core()

def load(kind, shapes):
    model = core.read_model(str(root / "ov" / f"meter_{kind}_model/model.pdmodel"))
    model.reshape(shapes)
    return core.compile_model(model, "CPU")

det = load("det", {"image":[1,3,608,608], "im_shape":[1,2], "scale_factor":[1,2]})
seg = load("seg", {"image":[1,3,512,512]})

def read(image_path, scales, overlay=None):
    image = cv2.imdecode(np.fromfile(image_path,np.uint8),1)
    if image is None: raise ValueError("Unreadable image")
    h,w = image.shape[:2]
    resized = cv2.resize(image,(608,608))/255
    x = ((resized-[.485,.456,.406])/[.229,.224,.225]).transpose(2,0,1)[None].astype("float32")
    inputs = dict(image=x,im_shape=np.float32([[608,608]]),scale_factor=np.float32([[608/h,608/w]]))
    rows = det(inputs)[det.output(0)]
    out=image.copy()
    records=[]
    for _,score,l,t,r,b in rows:
        if score<.5: continue
        l,r=np.clip([int(l),int(r)],0,w)
        t,b=np.clip([int(t),int(b)],0,h)
        if r<=l or b<=t: continue
        crop=cv2.resize(image[t:b,l:r],(512,512))
        tensor=(crop.astype("float32")/127.5-1).transpose(2,0,1)[None]
        logits=seg({"image":tensor})[seg.output(0)]
        mask=logits[0].argmax(axis=0).astype("uint8")
        region=out[t:b,l:r]
        labels=cv2.resize(mask,(r-l,b-t),interpolation=cv2.INTER_NEAREST)
        for cls,color in [(1,(0,0,255)),(2,(255,200,0))]:
            region[labels==cls]=color
        cv2.rectangle(out,(l,t),(r,b),(30,200,60),3)
        records.append(dict(score=float(score),bbox=list(map(int,[l,t,r,b])),needle_pixels=int((mask==1).sum()),tick_pixels=int((mask==2).sum())))
        matches = [s for s in scales if s["x"][0] <= (l+r)/(2*w) < s["x"][1]]
        if len(matches) != 1:
            records[-1]["status"]="manual_review"
            continue
        if matches:
            scale=matches[0]
            maximum,unit=scale["max"],scale["unit"]
            yy,xx=np.where(mask==1)
            yy_tick,xx_tick=np.where(mask==2)
            record=records[-1]
            record.update(unit=unit,scale_max=maximum)
            record["status"]="manual_review"
            if len(xx)>10 and len(xx_tick)>10:
                # Ellipse of tick pixels compensates for tilt and rectangular crops.
                (cx,cy),(width,height),rot=cv2.fitEllipse(np.column_stack((xx_tick,yy_tick)).astype("float32"))
                rad=np.radians(rot)
                def normalize(x,y):
                    return ((np.cos(rad)*(x-cx)+np.sin(rad)*(y-cy))/(width/2),
                            (-np.sin(rad)*(x-cx)+np.cos(rad)*(y-cy))/(height/2))
                u,v=normalize(xx,yy)
                radius=np.hypot(u,v)
                if np.quantile(radius,.95)>.60:
                    tip=radius>np.quantile(radius,.80)
                    theta=np.degrees(np.arctan2(np.median(v[tip]),np.median(u[tip])))+rot
                    # Dial endpoints observed at about 135 and 405 degrees clockwise.
                    fraction=((theta-scale["start_deg"])%360)/scale["span_deg"]
                    if fraction<=1:
                        record["status"]="read"
                        record["reading"]=round(scale["min"]+fraction*(maximum-scale["min"]),2)
                if "reading" not in record:
                    record["status"]="manual_review"
                label=f'{record["reading"]} {unit}' if "reading" in record else "manual review"
                cv2.putText(out,label,(l,max(30,t-8)),cv2.FONT_HERSHEY_SIMPLEX,max(.8,w/1500),(0,255,255),3)
    if w>1200: out=cv2.resize(out,(1200,round(h*1200/w)),interpolation=cv2.INTER_AREA)
    if overlay is not None: cv2.imencode(".jpg",out)[1].tofile(overlay)
    return records

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("image",type=Path)
    parser.add_argument("profile",type=Path)
    parser.add_argument("--overlay",type=Path)
    args=parser.parse_args()
    print(json.dumps(read(args.image,json.loads(args.profile.read_text(encoding="utf-8-sig")),args.overlay),indent=2))
