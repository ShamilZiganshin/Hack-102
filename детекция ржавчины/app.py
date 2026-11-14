from pathlib import Path
import io,json,re,threading,time,uuid
import numpy as np
from PIL import Image,ImageOps,UnidentifiedImageError
from flask import Flask,request,jsonify,render_template,send_from_directory,send_file
from rust_model import ROOT,DATA,RustSegmenter,save_result,overlay
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=40*1024*1024
MODEL=None;LOCK=threading.Lock();Image.MAX_IMAGE_PIXELS=24_000_000
@app.get('/')
def index():return render_template('index.html')
@app.get('/api/health')
def health():return jsonify(ok=True,device='CPU',model='UNet++ / ResNet50',offline=True)
@app.get('/api/examples')
def examples():
    rows=[]
    for p in sorted((ROOT/'outputs').glob('*/result.json')):
        if re.fullmatch(r'\d{2}',p.parent.name):rows.append({'id':p.parent.name,**json.loads(p.read_text(encoding='utf-8'))})
    return jsonify(rows)
@app.get('/api/benchmark')
def benchmark():
    p=ROOT/'outputs/benchmark.json';return jsonify(json.loads(p.read_text()) if p.exists() else {})
@app.get('/api/demo/<run>')
def demo(run):
    if not re.fullmatch(r'\d{2}',run):return jsonify(error='Неизвестный пример'),404
    p=ROOT/'outputs'/run/'result.json'
    if not p.exists():return jsonify(error='Пример ещё обрабатывается'),404
    return jsonify(run=run,**json.loads(p.read_text(encoding='utf-8')))
@app.get('/files/<run>/<name>')
def files(run,name):
    if not re.fullmatch(r'(\d{2}|[a-f0-9]{16})',run) or name not in ['original.jpg','overlay.jpg','mask.png','probability.png','heatmap.jpg','result.json']:return '',404
    return send_from_directory(ROOT/'outputs'/run,name)
@app.post('/api/analyze')
def analyze():
    global MODEL
    if 'image' not in request.files:return jsonify(error='Выберите фотографию'),400
    mode=request.form.get('mode','quality')
    if mode not in ['fast','quality','detail512']:return jsonify(error='Неизвестный режим'),400
    try:
        im=ImageOps.exif_transpose(Image.open(request.files['image'].stream)).convert('RGB')
        if im.width*im.height>24_000_000:return jsonify(error='Максимум 24 мегапикселя'),400
        rgb=np.array(im)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):return jsonify(error='Не удалось прочитать изображение. Используйте JPG, PNG или WebP.'),400
    with LOCK:
        if MODEL is None:MODEL=RustSegmenter()
        start=time.perf_counter();p=MODEL.predict(rgb,mode);elapsed=time.perf_counter()-start
        run=uuid.uuid4().hex[:16];out=ROOT/'outputs'/run
        result=save_result(rgb,p,out,meta={'image':Path(request.files['image'].filename or 'image').name,'mode':mode,'seconds':round(elapsed,3),'source':'User photograph; no ground truth available'})
        np.save(out/'probability.npy',p)
    return jsonify(run=run,**result)
@app.get('/api/export/<run>/<kind>')
def export(run,kind):
    if not re.fullmatch(r'(\d{2}|[a-f0-9]{16})',run) or kind not in ['mask','overlay']:return '',404
    try:threshold=float(request.args.get('threshold','.5'))
    except ValueError:return jsonify(error='Некорректный порог'),400
    if not .01<=threshold<=.99:return jsonify(error='Порог должен быть от 0.01 до 0.99'),400
    out=ROOT/'outputs'/run
    if not (out/'original.jpg').exists():return '',404
    p=np.load(out/'probability.npy') if (out/'probability.npy').exists() else np.array(Image.open(out/'probability.png')).astype(np.float32)/255
    mask=p>=threshold
    rgb=np.array(Image.open(out/'original.jpg').convert('RGB'))
    im=Image.fromarray(mask.astype(np.uint8)*255 if kind=='mask' else overlay(rgb,mask))
    b=io.BytesIO();im.save(b,format='PNG');b.seek(0)
    return send_file(b,mimetype='image/png',as_attachment=True,download_name=f'rust_{run}_{kind}_t{threshold:.2f}.png')
@app.errorhandler(413)
def too_large(e):return jsonify(error='Файл больше 40 МБ'),413
if __name__=='__main__':
    print('RustLab: http://127.0.0.1:8765',flush=True)
    app.run(host='127.0.0.1',port=8765,debug=False,threaded=True)
