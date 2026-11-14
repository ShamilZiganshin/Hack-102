from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import io
import threading
import numpy as np
from PIL import Image, ImageOps

gate = threading.Lock()
colors = {'rust': (255,112,47), 'oil': (49,211,225), 'crack': (242,74,170)}

def preview(handler, body, workers):
    if not all(workers.get(k) and workers[k].ready for k in colors):
        return handler.send({'error':'Модели загружаются. Проверьте журналы workers в outputs.'},status=503)
    if not gate.acquire(blocking=False):
        return handler.send({'error':'AR обрабатывает другой кадр'},status=429)
    try:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with Image.open(io.BytesIO(body)) as image:
                if image.width*image.height > 24000000:
                    raise ValueError('Слишком большой кадр')
                rgb = ImageOps.exif_transpose(image).convert('RGB')
            rgb.thumbnail((640,640))
            frame = root/'frame.png'
            rgb.save(frame)
            with ThreadPoolExecutor(3) as pool:
                jobs = {k:pool.submit(workers[k].infer,frame,root/(k+'.png'),'preview' if k=='oil' else 'fast256') for k in colors}
                for job in jobs.values(): job.result()
            array = np.array(rgb)
            blended = array.copy()
            findings = {}
            for key,color in colors.items():
                with Image.open(root/(key+'.png')) as image:
                    mask=np.asarray(image)>0
                findings[key] = {'present': bool(mask.any()), 'percent': round(float(mask.mean()) * 100, 2)}
                blended[mask]=array[mask]*.5+np.asarray(color)*.5
            buf=io.BytesIO()
            Image.fromarray(blended).save(buf,'JPEG',quality=87)
            if 'application/json' in handler.headers.get('Accept',''):
                return handler.send({'image':base64.b64encode(buf.getvalue()).decode('ascii'),'findings':findings})
            return handler.send(buf.getvalue(),'image/jpeg')
    finally:
        gate.release()
