from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import psycopg
cfg=json.loads((ROOT/'private/config.json').read_text(encoding='utf-8'))
with psycopg.connect(cfg['database']) as c:
 for metric,unit,low,high in [('temperature_c','C',10,75),('vibration_mm_s','mm/s',0,4.5),('pressure_out_bar','bar',2,10),('current_a','A',0,25)]:
  c.execute("INSERT INTO equipment_limits(equipment_id,metric,unit,lower_bound,upper_bound,source_locator,status) SELECT id,%s,%s,%s,%s,'KIBER102 DEMO: учебная уставка сценария, придумана для демонстрации; не ГОСТ','demo' FROM equipment WHERE tag LIKE 'AMS-PS-00%%' ON CONFLICT(equipment_id,metric,status) DO UPDATE SET lower_bound=EXCLUDED.lower_bound,upper_bound=EXCLUDED.upper_bound,source_locator=EXCLUDED.source_locator",(metric,unit,low,high))
print('16 demo limits, no approved limits changed')
