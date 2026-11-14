$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$projectPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $projectPython)) { throw 'Python environment missing. See README.md.' }
$localUrl='http://127.0.0.1:8765'
$serverReady=$false
try { $health=Invoke-RestMethod -Uri "$localUrl/api/health" -TimeoutSec 2; $serverReady=($health.model -eq 'UNet++ / ResNet50') } catch {}
if (!$serverReady) {
    $serverProcess=Start-Process -FilePath $projectPython -ArgumentList 'app.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'outputs\server.log') -RedirectStandardError (Join-Path $projectRoot 'outputs\server-error.log')
    $serverProcess.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\server.pid')
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        try { $health=Invoke-RestMethod -Uri "$localUrl/api/health" -TimeoutSec 1; if ($health.model -eq 'UNet++ / ResNet50') { $serverReady=$true; break } } catch {}
        Start-Sleep -Milliseconds 500
    }
}
if (!$serverReady) { throw 'Local server did not start. Check outputs/server-error.log.' }
Start-Process $localUrl
