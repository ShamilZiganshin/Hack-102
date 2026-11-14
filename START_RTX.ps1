$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$app=Join-Path $PSScriptRoot 'Насос — 3D и мобильный осмотр'
$py=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if(!(Test-Path $py)){throw 'Extract this update into the existing Kiber102-Windows-GPU directory beside .venv'}
$env:PUMP_DEVICE='cuda'
& $py -c "import torch; print(torch.cuda.get_device_name()); print(torch.ones(1,device='cuda').cpu())"
if($LASTEXITCODE){throw 'CUDA unavailable'}
Push-Location $app
try {
 function Check-Database([switch]$Quiet) {
  $probe="import backend; c=backend.db(); print(c.execute('select count(*) as n from v_equipment_passport').fetchone()); c.close()"
  if($Quiet){$probe="import sys" + [Environment]::NewLine + "try:" + [Environment]::NewLine + " " + $probe + [Environment]::NewLine + "except Exception: sys.exit(1)"
  }
  & $py -c $probe
  return
 }
 Check-Database -Quiet
 if($LASTEXITCODE){
  Write-Host "Starting the project database..."
  $data=Join-Path $app 'private/postgres'
  if(!(Test-Path "$data/PG_VERSION")){throw 'Check private/config.json and start the configured PostgreSQL instance'}
  $version=(Get-Content "$data/PG_VERSION").Trim()
  $ctl="$env:ProgramFiles/PostgreSQL/$version/bin/pg_ctl.exe"
  & $ctl -D $data status
  if($LASTEXITCODE){& $ctl -D $data -l "$app/private/postgres.log" -w start}
  Check-Database
  if($LASTEXITCODE){throw 'Configured database unavailable. See connection error above.'}
 }
 $listener=Get-NetTCPConnection -LocalPort 8769 -State Listen -ErrorAction SilentlyContinue
 if($listener){
  # Windows venv launchers and their child interpreter can have different PIDs.
  # Verify the actual script path using the listener's working directory.
  $owner=$listener.OwningProcess
  $verify=@"
import os,sys,psutil
from pathlib import Path
p=psutil.Process(int(sys.argv[1]))
target=Path(sys.argv[2]).resolve()
args=p.cmdline()[1:]
script=next((x for x in args if not x.startswith('-')),None)
if not script or p.name().lower() not in ('python.exe','pythonw.exe') or (Path(p.cwd())/script).resolve()!=target:
    sys.exit('Port 8769 belongs to a different program. No process was stopped.')
print('Restarting verified pump backend:',p.pid)
"@
  & $py -c $verify "$owner" "$app/backend.py"
  if($LASTEXITCODE){throw "Could not verify the backend on port 8769 (PID $owner). See message above."}
  & taskkill /PID $owner /T /F
  if($LASTEXITCODE){throw 'Could not stop prior stand'}
 }
 & $py setup.py
 if($LASTEXITCODE){throw 'HTTPS setup failed'}
 $p=Start-Process $py -WorkingDirectory $app -ArgumentList '-u backend.py' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$app/outputs/server.log" -RedirectStandardError "$app/outputs/server-error.log"
 $p.Id | Set-Content "$app/private/server.pid"
 for($i=0;$i -lt 90;$i++){
  if($p.HasExited){throw 'See outputs/server-error.log'}
  try{$h=Invoke-RestMethod http://127.0.0.1:8769/api/health -TimeoutSec 2;if($h.models.rust.ready -and $h.models.oil.ready -and $h.models.crack.ready){Write-Host 'READY. Open the second QR in the connection page.';return}}catch{}
  Start-Sleep 2
 }
 throw 'Check model startup logs in outputs'
}finally{Pop-Location}
