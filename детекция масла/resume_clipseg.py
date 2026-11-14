from pathlib import Path
import urllib.request,json,concurrent.futures,time
ROOT=Path(__file__).resolve().parent;target=ROOT/'models/clipseg/model.safetensors';part=target.with_suffix('.safetensors.part');meta=json.loads((ROOT/'research/clipseg_transfer.json').read_text());url=meta['url'];total=603049496
start=part.stat().st_size if part.exists() else 0
# The interrupted sequential transfer is an exact prefix. Four ranged workers
# fetch only the remaining bytes, then concatenate their ordered parts.
remaining=total-start;step=(remaining+3)//4
chunks=[(i,start+i*step,min(total-1,start+(i+1)*step-1)) for i in range(4) if start+i*step<total]
def fetch(task):
 index,lo,hi=task;p=target.parent/f'clipseg_chunk_{index}.part';expected=hi-lo+1
 for attempt in range(4):
  try:
   existing=p.stat().st_size if p.exists() else 0
   if existing==expected:return p
   req=urllib.request.Request(url,headers={'Range':f'bytes={lo+existing}-{hi}'})
   with urllib.request.urlopen(req,timeout=35) as response,p.open('ab') as out:
    if response.status!=206:raise RuntimeError('Server did not honor range')
    cr=response.headers.get('Content-Range','');print('Chunk',index,'range',cr,flush=True)
    if not cr.startswith(f'bytes {lo+existing}-'):raise RuntimeError('Unexpected range')
    while b:=response.read(1024*1024):out.write(b)
   if p.stat().st_size!=expected:raise RuntimeError('Incomplete chunk')
   print('Chunk complete',index,expected,flush=True);return p
  except Exception as e:print('Retry',index,str(e),flush=True)
 raise RuntimeError(f'Chunk {index} failed')
if __name__=='__main__':
 print('Resuming from',start,'of',total,flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:parts=list(ex.map(fetch,chunks))
 with part.open('ab') as out:
  for p in parts:
   with p.open('rb') as f:
    while b:=f.read(1024*1024):out.write(b)
 if part.stat().st_size!=total:raise RuntimeError('Final size mismatch')
 part.replace(target);print('Model ready',total,flush=True)
