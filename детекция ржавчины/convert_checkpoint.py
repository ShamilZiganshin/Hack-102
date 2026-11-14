"""Extract tensors without importing or executing model classes from a pickle."""
from pathlib import Path
import collections,pickle,types,torch,json,hashlib
ROOT=Path(__file__).resolve().parent
class Inert:
    def __setstate__(self,state): self.__dict__.update(state)
class Restricted(pickle.Unpickler):
    def find_class(self,module,name):
        if (module,name)==('collections','OrderedDict'):return collections.OrderedDict
        if (module,name) in [('__builtin__','set'),('builtins','set')]:return set
        if module=='torch' and name in ['FloatStorage','LongStorage','device','float32']:return getattr(torch,name)
        if module=='torch._utils' and name in ['_rebuild_parameter','_rebuild_tensor_v2']:return getattr(torch._utils,name)
        if module=='lightning_fabric.utilities.data' and name=='AttributeDict':return dict
        if (module=='corrosion.model' and name=='CorrosionModel') or module.startswith(('segmentation_models_pytorch.','torch.nn.modules.')) or (module=='torchvision.models.resnet' and name=='Bottleneck'):return Inert
        raise pickle.UnpicklingError(f'Blocked {module}.{name}')
def tensors(obj,prefix=''):
    out={}
    for key in ['_parameters','_buffers']:
        for name,value in getattr(obj,key,{}).items():
            if isinstance(value,torch.Tensor):out[prefix+name]=value.detach().cpu().contiguous()
    for name,child in getattr(obj,'_modules',{}).items():
        if child is not None:out.update(tensors(child,prefix+name+'.'))
    return out
if __name__=='__main__':
    mod=types.SimpleNamespace(__name__='restricted_tensor_extractor',Unpickler=Restricted,load=pickle.load)
    obj=torch.load(ROOT/'models/ostrava_original.pth',map_location='cpu',pickle_module=mod,weights_only=False)
    sd=tensors(obj);print('Tensors',len(sd),'head',[(k,tuple(v.shape)) for k,v in list(sd.items())[:8]],flush=True)
    torch.save(sd,ROOT/'models/ostrava_tensors.pt')
    print('Hparams',obj.__dict__.get('_hparams'),flush=True)
    print('Saved tensor-only checkpoint',flush=True)
