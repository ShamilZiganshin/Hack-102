import json
import sys
from gauge_reader import read

profile = [{'min':0, 'max':1.6, 'unit':'kPa', 'start_deg':135, 'span_deg':270, 'x':[0,1]}]
for line in sys.stdin:
    try:
        path, overlay = json.loads(line)
        response = {'gauges':read(path, profile, overlay)}
    except Exception as exc:
        response = {'error':str(exc)}
    print(json.dumps(response, ensure_ascii=True), flush=True)
