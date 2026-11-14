from pathlib import Path
import urllib.request,tarfile,json,time,hashlib,collections
ROOT=Path(__file__).resolve().parent;out=ROOT/'data/inspecsafe_audit';out.mkdir(parents=True,exist_ok=True)
class Limited:
 def __init__(self,stream,budget=32*1024*1024):self.stream=stream;self.budget=budget;self.n=0
 def read(self,n=-1):
  if self.n>=self.budget:raise RuntimeError('Audit download budget reached')
  b=self.stream.read(min(n if n>0 else 10240,self.budget-self.n));self.n+=len(b);return b
records=[];classes=collections.Counter();start=time.perf_counter();status=''
u='https://huggingface.co/datasets/1005xz/InspecSafe-V1/resolve/main/train.tar.gz'
try:
 response=urllib.request.urlopen(u,timeout=30);stream=Limited(response)
 with tarfile.open(fileobj=stream,mode='r|gz') as archive:
  for member in archive:
   if time.perf_counter()-start>180:status='Audit time budget reached';break
   if not member.isfile():continue
   name=member.name;suffix=Path(name).suffix.lower()
   print('Seen',name,member.size,flush=True)
   if suffix not in ['.jpg','.png','.json','.txt'] or member.size>8*1024*1024:continue
   if 'Annotations' not in name:continue
   b=archive.extractfile(member).read();key=hashlib.sha256(name.encode()).hexdigest()[:14];path=out/(key+suffix);path.write_bytes(b)
   rec={'original_path':name,'local':str(path.relative_to(ROOT)),'bytes':len(b),'role':'train_audit_not_test'}
   if suffix=='.json':
    try:
     obj=json.loads(b);labels=[s.get('label') for s in obj.get('shapes',[])];classes.update(labels);rec['labels']=labels
    except Exception as e:rec['parse_error']=str(e)
   records.append(rec)
   if len(records)>=36:status='36 annotation assets sampled';break
 response.close()
except Exception as e:status=str(e)
result={'source':u,'split':'train','audit_only':True,'status':status,'classes':dict(classes),'records':records,'seconds':time.perf_counter()-start}
(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('AUDIT',status,'ASSETS',len(records),'LABELS',dict(classes),flush=True)
