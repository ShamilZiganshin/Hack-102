from pathlib import Path
import time,json,traceback
from PIL import Image
from inspector import *
if __name__=='__main__':
    print('Waiting for local model download',flush=True)
    while True:
        try:
            r=session().get(OLLAMA+'/api/tags',timeout=5);r.raise_for_status()
            if any(m.get('name')==MODEL for m in r.json()['models']):break
        except Exception as e:print('Waiting:',e,flush=True)
        time.sleep(15)
    show=session().post(OLLAMA+'/api/show',json={'model':MODEL},timeout=20);show.raise_for_status()
    (ROOT/'research/model_info.json').write_text(json.dumps(show.json(),ensure_ascii=False,indent=2),encoding='utf-8')
    summary=[]
    for key in ['01','02','03']:
        print('START',key,flush=True)
        try:
            def progress(stage,n):
                if n%80==0:print(key,stage,n,flush=True)
            report=inspect(ROOT/'samples'/f'{key}.jpg',ROOT/'outputs'/key,progress)
            summary.append({'sample':key,'assessment':report['assessment'],'summary':report['summary'],'findings':report['findings'],'seconds':report['seconds']})
            print('RESULT',key,json.dumps(summary[-1],ensure_ascii=False),flush=True)
        except Exception as e:
            traceback.print_exc();summary.append({'sample':key,'error':str(e)})
        (ROOT/'outputs/demo_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    # An explicitly uninformative synthetic control, not a clean-equipment accuracy test.
    Image.new('RGB',(600,450),(127,127,127)).save(ROOT/'samples/uninformative_control.png')
    try:
        report=inspect(ROOT/'samples/uninformative_control.png',ROOT/'outputs/control')
        (ROOT/'outputs/control_check.json').write_text(json.dumps({'assessment':report['assessment'],'findings':report['findings'],'expected':'unclear; no invented equipment','pass':report['assessment']=='unclear' and not report['findings']},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception as e:print('CONTROL ERROR',e,flush=True)
    print('DONE',flush=True)
