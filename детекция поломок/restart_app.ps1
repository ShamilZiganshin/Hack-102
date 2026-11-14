$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$health=Invoke-RestMethod 'http://127.0.0.1:8767/api/health' -TimeoutSec 5
if ($health.active_jobs -gt 0) { throw 'Active user jobs exist; leave server running and retry after completion.' }
$serverId=[int](Get-Content -LiteralPath (Join-Path $projectRoot 'outputs\server.pid'))
$server=Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
$expectedPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!$server -or !$server.CommandLine.Contains($expectedPython) -or !$server.CommandLine.Contains('app.py')) { throw 'Server process identity mismatch; no process stopped.' }
$children=Get-CimInstance Win32_Process -Filter "ParentProcessId=$serverId" | Where-Object {$_.Name -eq 'python.exe'}
foreach($child in $children) { Stop-Process -Id $child.ProcessId -Force }
Stop-Process -Id $serverId -Force
$p=Start-Process -FilePath $expectedPython -ArgumentList 'app.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'outputs\server-8767.log') -RedirectStandardError (Join-Path $projectRoot 'outputs\server-8767-error.log')
$p.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\server.pid')
for ($i=0;$i -lt 30;$i++) {
 try { $updated=Invoke-RestMethod 'http://127.0.0.1:8767/api/health' -TimeoutSec 2; if ($updated.app_version -eq 'hybrid-v2') { $updated | ConvertTo-Json; exit 0 } } catch {}
 Start-Sleep -Milliseconds 500
}
throw 'Updated server did not start; inspect outputs/server-8767-error.log.'
