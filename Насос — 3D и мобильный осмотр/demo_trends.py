"""Rolling demonstration history, isolated from physical measurements."""
import math
import time
import threading
from datetime import datetime, timezone

KEYS=('temperature_c','vibration_mm_s','pressure_out_bar','current_a')
BASE=((53,2.1,6.5,18),(88,2.8,6.4,19),(62,3.1,1.4,22),(68,8.2,6.3,29))
TAGS=tuple(f'AMS-PS-00{i}' for i in range(1,5))
def sample(tag,t):
    return [round(v+a*math.sin(t/period),2) for v,a,period in zip(BASE[TAGS.index(tag)],(1.5,.25,.2,.4),(15,11,19,8))]

import recommendations
def import_archive(db):
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS pump_vibration_archive (
            profile int, seq int, source_time timestamp UNIQUE NOT NULL, rpm int,
            rms float8, x1 float8, x2 float8, hf float8, diagnosis text, PRIMARY KEY(profile,seq))""")
        with c.cursor() as cur:
            cur.executemany("""INSERT INTO pump_vibration_archive VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(profile,seq) DO UPDATE SET source_time=excluded.source_time,rpm=excluded.rpm,
                rms=excluded.rms,x1=excluded.x1,x2=excluded.x2,hf=excluded.hf,diagnosis=excluded.diagnosis""",
                [(i,j,r['time'],r['rpm'],r['rms'],r['x1'],r['x2'],r['hf'],r['diagnosis'])
                 for i,group in enumerate(recommendations.GROUPS) for j,r in enumerate(group)])
def latest(db,tag):
    rows=history(db,tag,True)
    return rows[-1] if rows else None
def writer(db):
    imported=False
    while True:
        try:
            if not imported:
                import_archive(db)
                imported=True
            with db() as c:
                c.execute('CREATE TABLE IF NOT EXISTS pump_demo_trend(tag text NOT NULL, tick bigint NOT NULL, vals double precision[] NOT NULL, PRIMARY KEY(tag,tick))')
                end=int(time.time())//5*5
                latest={r['tag']:r['last'] for r in c.execute('SELECT tag,max(tick) AS last FROM pump_demo_trend GROUP BY tag')}
                batch=[(tag,t,sample(tag,t)) for tag in TAGS for t in range(max(end-600,latest.get(tag,end-605)+5),end+1,5)]
                if batch:
                    with c.cursor() as cur:cur.executemany('INSERT INTO pump_demo_trend VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',batch)
                c.execute('DELETE FROM pump_demo_trend WHERE tick < %s',(end-86400,))
        except Exception as e:print('Demo history:',e,flush=True)
        time.sleep(5)

def history(db,tag,demo):
    if tag not in TAGS:return []
    with db() as c:
        if demo:
            profile=TAGS.index(tag)
            return c.execute("""SELECT t.tick,t.vals,a.rms,a.x1,a.x2,a.hf,a.rpm,to_char(a.source_time,'YYYY-MM-DD HH24:MI') AS time
                FROM pump_demo_trend t JOIN pump_vibration_archive a ON a.profile=%s AND a.seq=mod(t.tick/5,%s)
                WHERE t.tag=%s AND t.tick >= %s ORDER BY t.tick""",(profile,len(recommendations.GROUPS[profile]),tag,time.time()-600)).fetchall()
        return c.execute('SELECT extract(epoch FROM m.measured_at)::float8 AS tick, ARRAY[m.temperature_c,m.vibration_mm_s,m.pressure_out_bar,m.current_a] AS vals FROM measurements m JOIN equipment e ON e.id=m.equipment_id WHERE e.tag=%s AND m.measured_at >= now()-interval \'10 minutes\' AND m.data_origin=\'sensor_api\' ORDER BY m.measured_at',(tag,)).fetchall()
