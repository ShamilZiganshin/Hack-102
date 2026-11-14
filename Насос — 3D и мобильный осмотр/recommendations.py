import json
from pathlib import Path
HISTORY=json.loads(Path(__file__).with_name('vibration_history.json').read_text('utf8'))
RULES=(
 ('x1','Амплитуда 1×','мм/с',2.8,4.5,'Возможен дисбаланс ротора. Передайте данные вибродиагносту для проверки рабочего колеса.'),
 ('x2','Амплитуда 2×','мм/с',1.8,3.0,'Возможна расцентровка. Запросите проверку центровки муфты и крепления опор.'),
 ('hf','ВЧ-шум','g',2.5,None,'Возможны кавитация или износ подшипника. Запросите повторный замер спектра для уточнения причины.'))
def evaluate(spectrum,metrics):
 alerts=[]
 for key,label,unit,warn,alarm,advice in RULES:
  value=spectrum.get(key)
  if value is None or value<=warn:continue
  severe=alarm is not None and value>alarm
  alerts.append(dict(label=label,value=value,unit=unit,limit=alarm if severe else warn,direction='выше',level='Тревога' if severe else 'Предупреждение',advice=advice))
 actions={'temperature_c':'Сверьте температуру с независимым измерением и передайте отклонение ответственному за осмотр.','pressure_out_bar':'Сверьте показание с манометром и проверьте журнал режима подачи.','current_a':'Запросите проверку нагрузки привода.','vibration_mm_s':'Повторите замер вибрации и сравните спектр с предыдущим осмотром.'}
 for m in metrics:
  if m['state']!='outside':continue
  lo=m['limit']['lower_bound'];low=lo is not None and m['value']<float(lo)
  alerts.append(dict(label=m['label'],unit=m['unit'],value=m['value'],limit=float(lo if low else m['limit']['upper_bound']),direction='ниже' if low else 'выше',level='Выход за уставку',advice=actions.get(m['metric'],'Проверьте измерение.')))
 return alerts
def profile(r):
 if r['x1']>2.8:return 1
 if r['x2']>1.8:return 2
 if r['hf']>2.5:return 3
 return 0
GROUPS=[[r for r in HISTORY if profile(r)==i] for i in range(4)]
