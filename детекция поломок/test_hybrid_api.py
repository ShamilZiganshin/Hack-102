from pathlib import Path
from app import app,Q,JOBS
from unittest.mock import patch
client=app.test_client()
for v in ['bad','nan','1','0.01']:
 r=client.post('/api/jobs',data={'engine':'hybrid','example':'02','candidate_threshold':v});assert r.status_code==400,(v,r.status_code)
with patch.object(Q,'put') as put:
 r=client.post('/api/jobs',data={'engine':'hybrid','example':'02','candidate_threshold':'.4'});assert r.status_code==202,r.get_data(as_text=True);assert r.json['engine']=='hybrid' and r.json['candidate_threshold']==.4;put.assert_called_once();key=r.json['id'];JOBS[key].update(status='error',error='API validation test; inference intentionally not run.')
 assert client.get('/api/jobs/'+key).status_code==200
for u in ['/detectors','/static/detectors.js','/api/specialists/hybrid/invalid','/specialist-files/hybrid/02/mask_0.png']:
 r=client.get(u);assert r.status_code==(404 if u.endswith('invalid') else 200),(u,r.status_code)
print('Hybrid API passed: engine, threshold validation, static UI and safe sample IDs.')
