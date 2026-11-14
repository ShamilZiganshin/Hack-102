from pathlib import Path
import sys,subprocess,json,webbrowser,time,urllib.request,os
ROOT=Path(__file__).resolve().parent;PG=Path('C:/Program Files/PostgreSQL/18/bin');flags=0x08000000
def run(args):subprocess.run([str(x) for x in args],check=True,creationflags=flags)
status=subprocess.run([str(PG/'pg_ctl.exe'),'-D',str(ROOT/'private/postgres'),'status'],capture_output=True,creationflags=flags)
if status.returncode:run([PG/'pg_ctl.exe','-D',ROOT/'private/postgres','-l',ROOT/'private/postgres.log','start'])
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:opener.open('http://127.0.0.1:8769/api/health',timeout=2);running=True
except Exception:running=False
if not running:
 run([sys.executable,ROOT/'setup.py'])
 out=open(ROOT/'outputs/server.log','ab');err=open(ROOT/'outputs/server-error.log','ab')
 p=subprocess.Popen([sys.executable,'-u',str(ROOT/'backend.py')],cwd=ROOT,stdout=out,stderr=err,creationflags=flags)
 (ROOT/'private/server.pid').write_text(str(p.pid))
 for i in range(30):
  try:opener.open('http://127.0.0.1:8769/api/health',timeout=1);break
  except Exception:time.sleep(1)
# Existing crack app is left intact; start only when unavailable.
try:opener.open('http://127.0.0.1:8767/api/health',timeout=3)
except Exception:
 crack=ROOT.parent/'детекция поломок'
 subprocess.Popen(['powershell.exe','-NoProfile','-File',str(crack/'launch.ps1')],cwd=crack,creationflags=flags,stdout=open(ROOT/'outputs/crack-launch.log','ab'),stderr=subprocess.STDOUT)
webbrowser.open((ROOT/'Насос — свободный 3D.html').as_uri());webbrowser.open((ROOT/'Подключить телефон.html').as_uri())
