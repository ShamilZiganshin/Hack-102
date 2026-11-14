$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$projectPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
$localUrl='http://127.0.0.1:8766'
$ready=$false
try { $health=Invoke-RestMethod -Uri "$localUrl/api/health" -TimeoutSec 2; $ready=($health.project -eq 'oiltrace') } catch {}
if (!$ready) {
 $serverProcess=Start-Process -FilePath $projectPython -ArgumentList 'app.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'outputs\server.log') -RedirectStandardError (Join-Path $projectRoot 'outputs\server-error.log')
 $serverProcess.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\server.pid')
 for ($attempt=0;$attempt -lt 60;$attempt++) {
  try { $health=Invoke-RestMethod -Uri "$localUrl/api/health" -TimeoutSec 1; if ($health.project -eq 'oiltrace') {$ready=$true;break} } catch {}
  Start-Sleep -Milliseconds 500
 }
}
if (!$ready) {throw 'Server did not start. Check outputs/server-error.log.'}
Start-Process $localUrl
