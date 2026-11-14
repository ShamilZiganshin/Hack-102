from pathlib import Path
import tempfile,json
from PIL import Image
from hybrid import validate_reviews,compose_result
ids=[1,2]
good={'reviews':[{'id':1,'decision':'confirmed','evidence':'Виден раскрытый разрыв.'},{'id':2,'decision':'rejected','evidence':'Повторяющееся ребро корпуса.'}]}
r=validate_reviews(good,ids);assert r[1]['decision']=='confirmed' and r[2]['decision']=='rejected'
for bad in [{'reviews':[]},{'reviews':[good['reviews'][0],good['reviews'][0]]},{'reviews':[{'id':9,'decision':'confirmed','evidence':'x'}]}]:
 try:validate_reviews(bad,ids)
 except ValueError:pass
 else:raise AssertionError('Invalid review was accepted')
root=Path.cwd()/'outputs/hybrid_filter_test';src=root/'candidates';out=root/'result';src.mkdir(parents=True,exist_ok=True);out.mkdir(exist_ok=True)
for i in range(3):
 im=Image.new('L',(12,12),0);im.putpixel((i,i),255);im.save(src/f'mask_{i}.png')
original=Image.new('RGB',(12,12),(100,100,100));original.save(src/'overlay.jpg')
source={'size':[12,12],'seconds':.1,'detections':[{'class':'crack','confidence':.8,'box':[0,0,5,5]} for _ in range(3)]}
reviews={1:{'id':1,'decision':'confirmed','evidence':'gap'},2:{'id':2,'decision':'rejected','evidence':'rib'},3:{'id':3,'decision':'uncertain','evidence':'unclear'}}
report=compose_result(original,src,out,source,reviews,.25,1,[],[],None);mask=Image.open(out/'mask.png');assert mask.getpixel((0,0))==255 and mask.getpixel((1,1))==0 and mask.getpixel((2,2))==0
assert report['verification']['confirmed']==1 and report['verification']['rejected']==1 and report['verification']['uncertain']==1
print('Passed: strict IDs, missing reviews, and exclusion of rejected/uncertain pixels in the exported mask.')
