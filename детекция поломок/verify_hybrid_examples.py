from pathlib import Path
from hybrid import run
ROOT=Path.cwd()
cases=[('02',ROOT/'samples/02.jpg',ROOT/'outputs/specialists/crack_n/02'),('e04',ROOT/'samples/test_photos/e04.jpg',ROOT/'outputs/specialists/crack_n/e04'),('casing',ROOT/'samples/reported_casing.jpg',ROOT/'outputs/0b759d03a0204ee8')]
for key,image,candidates in cases:
 print('START',key,flush=True)
 def progress(stage,tokens=0,**details):
  if tokens%80==0:print(key,stage,tokens,details,flush=True)
 try:
  result=run(image,ROOT/'outputs/specialists/hybrid'/key,.25,progress,candidates)
  print('RESULT',key,result['verification'],flush=True)
 except Exception as e:print('ERROR',key,repr(e),flush=True)
print('ALL DONE',flush=True)
