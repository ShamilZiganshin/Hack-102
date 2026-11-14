from pathlib import Path
import json
from specialist_yolo import run
r=Path.cwd();rows=json.loads((r/'samples/test_photos/sources.json').read_text(encoding='utf-8'));result=[]
for row in rows:
 if 'error' in row:continue
 out=run('crack_n',r/'samples/test_photos'/f"{row['id']}.jpg",r/'outputs/specialists/crack_n'/row['id'])
 result.append({'id':row['id'],'title':row['title'],'kind':row['kind'],**out});print(row['id'],[(v['class'],round(v['confidence'],3)) for v in out['detections'] if v['confidence']>=.25],round(out['seconds'],2),flush=True)
(r/'outputs/specialists/external_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
