from pathlib import Path
import io,json,re,threading,uuid
import numpy as np
from PIL import Image,ImageOps,UnidentifiedImageError
from flask import Flask,request,jsonify,render_template,send_file,send_from_directory
_open_image=Image.open
from oil_model import ROOT,OilDetector,save_prediction,load_result_mask,overlay
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=32*1024*1024
Image.MAX_IMAGE_PIXELS=24_000_000
MODELS={};LOCK=threading.Lock()
def valid_run(run):return bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,70}',run))
@app.get('/')
def index():return render_template('index.html')
@app.get('/api/health')
def health():return jsonify(ok=True,project='oiltrace',device='CPU',automatic=True,offline=True)
@app.get('/api/examples')
def examples():return jsonify(json.loads((ROOT/'samples/sources.json').read_text(encoding='utf-8')))
@app.get('/api/demo/<sample>')
def demo(sample):
 variant=request.args.get('model','nano')
 if variant not in ['nano','medium','clipseg','hybrid'] or not valid_run(sample):return '',404
 run=f'{variant}_{sample}';path=ROOT/'outputs'/run/'result.json'
 if not path.exists():return jsonify(error='Пример ещё обрабатывается'),404
 return jsonify(run=run,**json.loads(path.read_text(encoding='utf-8')))
@app.get('/files/<run>/<name>')
def files(run,name):
 if not valid_run(run) or name not in ['original.jpg','overlay.jpg','mask.png','scoremap.png','result.json']:return '',404
 return send_from_directory(ROOT/'outputs'/run,name)
@app.post('/api/analyze')
def analyze():
 if 'image' not in request.files:return jsonify(error='Выберите фотографию'),400
 variant=request.form.get('model','nano')
 try:imgsz=int(request.form.get('imgsz','960'))
 except ValueError:return jsonify(error='Некорректное разрешение'),400
 if variant not in ['nano','medium','clipseg','hybrid'] or imgsz not in [640,960,1280]:return jsonify(error='Некорректный режим'),400
 try:
  with _open_image(request.files['image'].stream) as src:
   if src.width*src.height>24_000_000:return jsonify(error='Фото больше 24 мегапикселей'),400
   im=ImageOps.exif_transpose(src).convert('RGB');source_size=im.size;im.thumbnail((2048,2048),Image.Resampling.LANCZOS);rgb=np.array(im)
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError):return jsonify(error='Не удалось прочитать фото. Используйте JPG, PNG или WebP.'),400
 with LOCK:
  if variant not in MODELS:
   if variant in ['clipseg','hybrid']:
    from surface_model import SurfaceOilModel
    MODELS[variant]=SurfaceOilModel(hybrid=variant=='hybrid')
   else:MODELS[variant]=OilDetector(variant)
  result=MODELS[variant].predict(rgb,imgsz);run=uuid.uuid4().hex[:16]
  save_fn=save_prediction
  if result.get('kind')=='semantic':
   from surface_model import save_surface_prediction
   save_fn=save_surface_prediction
  meta=save_fn(rgb,result,ROOT/'outputs'/run,{'image':Path(request.files['image'].filename or 'photo').name,'ground_truth':False,'source_size':source_size,'source':'user photograph'})
 return jsonify(run=run,**meta)
@app.get('/api/export/<run>/<kind>')
def export(run,kind):
 if not valid_run(run) or kind not in ['mask','overlay','json']:return '',404
 try:threshold=float(request.args.get('threshold','.8'))
 except ValueError:return jsonify(error='Некорректный порог'),400
 if not .05<=threshold<=.99:return jsonify(error='Порог от 0.05 до 0.99'),400
 out=ROOT/'outputs'/run
 if not (out/'instances.npz').exists() and not (out/'dense_score.npy').exists():return '',404
 if (out/'dense_score.npy').exists():
  meta=json.loads((out/'result.json').read_text(encoding='utf-8'));mask=np.load(out/'dense_score.npy')>=threshold
 else:mask,meta=load_result_mask(out,threshold)
 selected=[d for d in meta['detections'] if d['confidence']>=threshold]
 if kind=='json':
  data={**meta,'confidence_threshold':threshold,'detections':selected,'count':int(mask.any()) if meta.get('kind')=='semantic' else len(selected),'status':'suspected_oil' if mask.any() else 'no_detection','mask_percent_of_image':float(mask.mean()*100)}
  b=io.BytesIO(json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8'));return send_file(b,mimetype='application/json',as_attachment=True,download_name=f'oil_{run}_t{threshold:.2f}.json')
 rgb=np.array(Image.open(out/'original.jpg').convert('RGB'));im=Image.fromarray(mask.astype(np.uint8)*255 if kind=='mask' else overlay(rgb,mask));b=io.BytesIO();im.save(b,format='PNG');b.seek(0)
 return send_file(b,mimetype='image/png',as_attachment=True,download_name=f'oil_{run}_{kind}_t{threshold:.2f}.png')
@app.errorhandler(413)
def too_large(error):return jsonify(error='Файл больше 32 МБ'),413
if __name__=='__main__':app.run(host='127.0.0.1',port=8766,debug=False,threaded=True)

