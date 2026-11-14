"""Extract tensors and plain configuration; do not import classes stored in pickle."""
from pathlib import Path
import collections,pickle,types,json,torch
ROOT=Path(__file__).resolve().parent
class Inert:
 def __init__(self,*args,**kwargs):self.__dict__.update(kwargs)
 def __setstate__(self,state):self.__dict__.update(state)
class Restricted(pickle.Unpickler):
 def find_class(self,module,name):
  if (module,name)==('collections','OrderedDict'):return collections.OrderedDict
  if (module,name) in [('__builtin__','set'),('builtins','set')]:return set
  if module=='torch' and name in ['FloatStorage','HalfStorage','LongStorage','device','Size']:return getattr(torch,name)
  if module=='torch._utils' and name in ['_rebuild_parameter','_rebuild_tensor_v2']:return getattr(torch._utils,name)
  if module=='ultralytics.utils' or module.startswith(('ultralytics.nn.','ultralytics.utils.','torch.nn.modules.')):return Inert
  raise pickle.UnpicklingError(f'Blocked {module}.{name}')
def tensors(obj,prefix=''):
 out={}
 for key in ['_parameters','_buffers']:
  for name,value in getattr(obj,key,{}).items():
   if isinstance(value,torch.Tensor):out[prefix+name]=value.detach().cpu().contiguous().clone()
 for name,child in getattr(obj,'_modules',{}).items():
  if child is not None:out.update(tensors(child,prefix+name+'.'))
 return out
if __name__=='__main__':
 from safetensors.torch import save_file
 for name in ['spill_leak_nano','spill_leak']:
  mod=types.SimpleNamespace(__name__='restricted_tensor_extractor',Unpickler=Restricted,load=pickle.load)
  ckpt=torch.load(ROOT/'models'/f'{name}_original.pt',map_location='cpu',pickle_module=mod,weights_only=False)
  model=ckpt.get('ema') or ckpt['model'];sd=tensors(model)
  metadata={'architecture':model.yaml,'names':model.names,'train_args':ckpt.get('train_args'),'train_metrics':ckpt.get('train_metrics'),'epoch':ckpt.get('epoch'),'date':ckpt.get('date'),'version':ckpt.get('version')}
  (ROOT/'models'/f'{name}.json').write_text(json.dumps(metadata,indent=2,default=str),encoding='utf-8')
  save_file(sd,str(ROOT/'models'/f'{name}.safetensors'))
  print(name,'tensors',len(sd),'classes',model.names,'scale',model.yaml.get('scale'),'data',ckpt.get('train_args',{}).get('data'),'metrics',ckpt.get('train_metrics'),flush=True)

