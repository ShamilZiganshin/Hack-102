import urllib.request,pathlib,time,concurrent.futures,zipfile,json
ROOT=pathlib.Path(__file__).resolve().parent
TASKS={
 'models/ostrava_original.pth':'https://dagshub.com/matejfric/corrosion.mlflow/api/2.0/mlflow-artifacts/artifacts/fbe6a559d6024dd9b2298c1fa5a30aa8/aa88cf5d7b174fd4840d3851af51509f/artifacts/model/data/model.pth',
 'research/ostrava_dataset.zip':'https://zenodo.org/api/records/11235637/files/corrosion-in-industrial-complexes-in-ostrava.zip/content',
 'repositories/ostrava.zip':'https://codeload.github.com/matejfric/corrosion-segmentation/zip/5af4a651ac1c97a67b23f71bbeb9def1e43f1ea2',
 'repositories/spotrust.zip':'https://codeload.github.com/StuvX/SpotRust/zip/refs/heads/master',
}
def fetch(task):
 name,url=task; p=ROOT/name; p.parent.mkdir(parents=True,exist_ok=True)
 for attempt in range(5):
  try:
   print('Download',name,'attempt',attempt+1,flush=True)
   req=urllib.request.Request(url,headers={'User-Agent':'RustLab-local-demo/1.0'})
   with urllib.request.urlopen(req,timeout=60) as r, p.with_suffix(p.suffix+'.part').open('wb') as out:
    n=0
    while b:=r.read(1024*1024):out.write(b);n+=len(b)
   p.with_suffix(p.suffix+'.part').replace(p);print('Saved',name,n,flush=True)
   return
  except Exception as e:print('Retry',name,str(e),flush=True);time.sleep(2)
 raise RuntimeError(name)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(fetch,TASKS.items()))
 for n in ['ostrava','spotrust']:
  with zipfile.ZipFile(ROOT/'repositories'/f'{n}.zip') as z:z.extractall(ROOT/'repositories'/n)
 with zipfile.ZipFile(ROOT/'research/ostrava_dataset.zip') as z:
  print('DATASET FILES',z.namelist()[:25],flush=True)
  for f in z.namelist():
   if '/test/' in f or '/valid/' in f or f.lower().endswith(('.md','.txt')):z.extract(f,ROOT/'data')
