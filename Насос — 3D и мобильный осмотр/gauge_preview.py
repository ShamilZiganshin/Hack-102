import base64
import json
import subprocess
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from PIL import Image, ImageOps

lock = threading.Lock()
folder = Path(__file__).resolve().parent / 'gauge'
python = folder.parent.parent / '.venv-gauge/Scripts/python.exe'
worker = None

def analyze(path, overlay):
    global worker
    if worker is None or worker.poll() is not None:
        worker = subprocess.Popen([str(python), '-u', str(folder/'live.py')],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                  encoding='utf-8')
    worker.stdin.write(json.dumps([str(path), str(overlay)])+'\n')
    worker.stdin.flush()
    line = worker.stdout.readline()
    if not line:
        raise RuntimeError('Процесс чтения манометра завершился')
    response = json.loads(line)
    if 'error' in response:
        raise ValueError(response['error'])
    return response['gauges']

def preview_gauge(handler, body):
    if not lock.acquire(blocking=False):
        return handler.send({'error':'Манометр обрабатывает другой кадр'},status=429)
    try:
        with TemporaryDirectory() as tmp, Image.open(BytesIO(body)) as image:
            if image.width*image.height > 24000000:
                raise ValueError('Слишком большой кадр')
            frame = ImageOps.exif_transpose(image).convert('RGB')
            frame.thumbnail((960,960))
            path = Path(tmp)/'frame.png'
            overlay = Path(tmp)/'result.jpg'
            frame.save(path)
            gauges = analyze(path, overlay)
            return handler.send({'image':base64.b64encode(overlay.read_bytes()).decode('ascii'),
                                 'gauges':gauges})
    finally:
        lock.release()
