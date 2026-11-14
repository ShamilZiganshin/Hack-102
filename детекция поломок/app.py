from pathlib import Path
import json,queue,threading,time,uuid,re,io,subprocess,sys
from PIL import Image,ImageOps,UnidentifiedImageError
from flask import Flask,request,jsonify,render_template,send_from_directory
from inspector import ROOT,MODEL,OLLAMA,session,inspect
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=25*1024*1024
Image.MAX_IMAGE_PIXELS=16_000_000
JOBS={};Q=queue.Queue();MUTEX=threading.Lock()
def write_status(job):
    p=ROOT/'outputs'/job['id']/'status.json';p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
def worker():
    while True:
        key,path,context=Q.get();job=JOBS[key];job['started']=time.time();job['status']='analyzing';write_status(job)
        def update(stage,tokens=0,**details):
            job.update(status=stage,tokens=tokens,**details)
        try:
            engine=job.get('engine','qwen')
            if engine=='qwen':result=inspect(path,ROOT/'outputs'/key,update,context)
            elif engine=='hybrid':
                from hybrid import run as hybrid_run
                result=hybrid_run(path,ROOT/'outputs'/key,job.get('candidate_threshold',.25),update)
            else:
                if engine=='pipeline':cmd=[sys.executable,str(ROOT/'specialist_pipeline.py'),'--image',str(path),'--out',str(ROOT/'outputs'/key)]
                else:
                    runtime=ROOT.parent/'детекция масла/.venv/Scripts/python.exe'
                    if not runtime.exists():raise RuntimeError('Не найдено локальное YOLO-окружение. См. README.')
                    cmd=[str(runtime),str(ROOT/'specialist_yolo.py'),'--model',engine,'--image',str(path),'--out',str(ROOT/'outputs'/key),'--size','960']
                with (ROOT/'outputs'/key/'inference.log').open('w',encoding='utf-8') as log:
                    proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
                if proc.returncode:raise RuntimeError('Детектор завершился с ошибкой. См. outputs/'+key+'/inference.log')
                result=json.loads((ROOT/'outputs'/key/'result.json').read_text(encoding='utf-8'))
            job.update(status='completed',result=result,finished=time.time());write_status(job)
        except Exception as e:
            job.update(status='error',error=str(e),finished=time.time());write_status(job)
        finally:Q.task_done()
threading.Thread(target=worker,daemon=True).start()
@app.get('/')
def index():return render_template('index.html')
@app.get('/detectors')
def detectors():return render_template('detectors.html')
@app.get('/api/specialists/<engine>/<sample>')
def specialist_demo(engine,sample):
    if engine not in ['hybrid','crack_n','crack_m','industrial','pipeline'] or not re.fullmatch(r'(0[123]|e0[1-9]|casing)',sample):return '',404
    p=ROOT/'outputs/specialists'/engine/sample/'result.json'
    if not p.exists():return jsonify(error='Этот пример ещё не готов'),404
    return jsonify(id=sample,**json.loads(p.read_text(encoding='utf-8')))
@app.get('/specialist-files/<engine>/<sample>/<name>')
def specialist_files(engine,sample,name):
    if engine not in ['hybrid','crack_n','crack_m','industrial','pipeline'] or not re.fullmatch(r'(0[123]|e0[1-9]|casing)',sample):return '',404
    if name not in ['original.jpg','overlay.jpg','mask.png','result.json','candidates.jpg','review_progress.json'] and not re.fullmatch(r'mask_[0-9]+\.png',name):return '',404
    return send_from_directory(ROOT/'outputs/specialists'/engine/sample,name)
@app.get('/api/test-photos')
def test_photos():
    return jsonify([v for v in json.loads((ROOT/'samples/test_photos/sources.json').read_text(encoding='utf-8')) if 'error' not in v])
@app.get('/test-photos/<key>.jpg')
def test_photo(key):
    if not re.fullmatch(r'e0[1-9]',key):return '',404
    return send_from_directory(ROOT/'samples/test_photos',key+'.jpg')
@app.get('/api/health')
def health():
    try:
        r=session().get(OLLAMA+'/api/tags',timeout=3);r.raise_for_status();models=r.json().get('models',[])
        installed=any(m.get('name')==MODEL for m in models)
        return jsonify(ok=True,app_version='hybrid-v2',hybrid=True,ollama=True,installed=installed,model=MODEL,device='CPU',active_jobs=sum(j['status'] not in ['completed','error'] for j in JOBS.values()))
    except Exception as e:return jsonify(ok=True,app_version='hybrid-v2',hybrid=True,ollama=False,installed=False,model=MODEL,device='CPU',error=str(e))
@app.get('/api/examples')
def examples():
    rows=[]
    for i in ['01','02','03']:
        p=ROOT/'outputs'/i/'result.json'
        rows.append({'id':i,'title':{'01':'Фото 1 · корпус','02':'Фото 2 · труба','03':'Фото 3 · изоляция'}[i],'ready':p.exists()})
    return jsonify(rows)
@app.get('/api/results/<key>')
def results(key):
    if not re.fullmatch(r'(0[123]|[a-f0-9]{16})',key):return jsonify(error='Неизвестный результат'),404
    p=ROOT/'outputs'/key/'result.json'
    if not p.exists():return jsonify(error='Ответ модели ещё не готов'),404
    return jsonify(id=key,**json.loads(p.read_text(encoding='utf-8')))
@app.get('/samples/<key>.jpg')
def samples(key):
    if key=='casing':return send_from_directory(ROOT/'samples','reported_casing.jpg')
    if key not in ['01','02','03']:return '',404
    return send_from_directory(ROOT/'samples',key+'.jpg')
@app.get('/files/<key>/<name>')
def files(key,name):
    if not re.fullmatch(r'(0[123]|[a-f0-9]{16})',key) or (name not in ['original.jpg','annotated.jpg','result.json','raw_response.txt','overlay.jpg','mask.png','candidates.jpg','review_progress.json'] and not re.fullmatch(r'mask_[0-9]+\.png',name)):return '',404
    return send_from_directory(ROOT/'outputs'/key,name,as_attachment=name in ['result.json','raw_response.txt'])
@app.post('/api/jobs')
def create_job():
    origin=request.headers.get('Origin')
    if origin and origin not in ['http://127.0.0.1:8767','http://localhost:8767']:return jsonify(error='Запрос с другого сайта отклонён'),403
    if Q.qsize()>=3:return jsonify(error='Очередь заполнена. Дождитесь текущих результатов.'),429
    engine=request.form.get('engine','qwen')
    if engine not in ['qwen','hybrid','crack_n','crack_m','industrial','pipeline']:return jsonify(error='Неизвестная модель'),400
    try:candidate_threshold=float(request.form.get('candidate_threshold','.25'))
    except ValueError:return jsonify(error='Некорректный порог кандидатов'),400
    if not .05<=candidate_threshold<=.95:return jsonify(error='Порог кандидатов должен быть от 0.05 до 0.95'),400
    key=uuid.uuid4().hex[:16];out=ROOT/'outputs'/key
    example=request.form.get('example');context=request.form.get('context','').strip()[:1200]
    if example in ['01','02','03']:path=ROOT/'samples'/f'{example}.jpg'
    elif example=='casing':path=ROOT/'samples/reported_casing.jpg'
    elif re.fullmatch(r'e0[1-9]',example or '') and (ROOT/'samples/test_photos'/f'{example}.jpg').exists():path=ROOT/'samples/test_photos'/f'{example}.jpg'
    elif 'image' in request.files:
        upload=request.files['image']
        try:
            with Image.open(upload.stream) as im:
                if im.width*im.height>16_000_000:return jsonify(error='Максимум 16 мегапикселей'),400
                im=ImageOps.exif_transpose(im).convert('RGB');out.mkdir(parents=True,exist_ok=True);path=out/'input.jpg';im.save(path,quality=96)
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):return jsonify(error='Не удалось прочитать изображение. Используйте JPG, PNG или WebP.'),400
    else:return jsonify(error='Сначала выберите фотографию'),400
    job={'id':key,'engine':engine,'candidate_threshold':candidate_threshold,'status':'queued','created':time.time(),'tokens':0,'image':path.name}
    JOBS[key]=job;write_status(job);Q.put((key,path,context));return jsonify(job),202
@app.get('/api/jobs/<key>')
def job(key):
    if not re.fullmatch(r'[a-f0-9]{16}',key):return '',404
    if key in JOBS:return jsonify({**JOBS[key],'elapsed':round(time.time()-JOBS[key].get('started',JOBS[key]['created']),1)})
    p=ROOT/'outputs'/key/'status.json'
    if not p.exists():return '',404
    j=json.loads(p.read_text(encoding='utf-8'))
    if j['status'] not in ['completed','error']:j.update(status='error',error='Приложение было перезапущено. Запустите анализ заново.')
    return jsonify(j)
@app.errorhandler(413)
def large(e):return jsonify(error='Файл больше 25 МБ'),413
if __name__=='__main__':
    print('InspectLab: http://127.0.0.1:8767',flush=True);app.run(host='127.0.0.1',port=8767,threaded=True,debug=False)
