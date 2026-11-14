$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$projectPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
$ollamaExe=Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (!(Test-Path -LiteralPath $projectPython)) { throw 'Python environment missing. See README.md.' }
if (!(Test-Path -LiteralPath $ollamaExe)) { throw 'Ollama is not installed. Install it from https://ollama.com/download/windows' }
$env:OLLAMA_HOST='127.0.0.1:11435'
$env:OLLAMA_MODELS=Join-Path $projectRoot 'models'
$env:OLLAMA_NO_CLOUD='1'
$env:OLLAMA_CONTEXT_LENGTH='4096'
$ollamaReady=$false
try { $version=Invoke-RestMethod 'http://127.0.0.1:11435/api/version' -TimeoutSec 2; $ollamaReady=!!$version.version } catch {}
if (!$ollamaReady) {
 $p=Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'outputs\ollama.log') -RedirectStandardError (Join-Path $projectRoot 'outputs\ollama-error.log')
 $p.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\ollama.pid')
 for ($attempt=0;$attempt -lt 40;$attempt++) {
  try { $version=Invoke-RestMethod 'http://127.0.0.1:11435/api/version' -TimeoutSec 1; if ($version.version) {$ollamaReady=$true;break} } catch {}
  Start-Sleep -Milliseconds 500
 }
}
if (!$ollamaReady) { throw 'Ollama failed to start. See outputs/ollama-error.log.' }
$models=Invoke-RestMethod 'http://127.0.0.1:11435/api/tags'
if (!($models.models | Where-Object {$_.name -eq 'qwen3-vl:4b-instruct'})) { throw 'Model missing. Run DOWNLOAD_MODEL.bat first.' }
$appReady=$false
try { $health=Invoke-RestMethod 'http://127.0.0.1:8767/api/health' -TimeoutSec 2; $appReady=($health.model -eq 'qwen3-vl:4b-instruct') } catch {}
if (!$appReady) {
 $p=Start-Process -FilePath $projectPython -ArgumentList 'app.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'outputs\server.log') -RedirectStandardError (Join-Path $projectRoot 'outputs\server-error.log')
 $p.Id | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\server.pid')
 for ($attempt=0;$attempt -lt 40;$attempt++) {
  try { $health=Invoke-RestMethod 'http://127.0.0.1:8767/api/health' -TimeoutSec 1; if ($health.model -eq 'qwen3-vl:4b-instruct') {$appReady=$true;break} } catch {}
  Start-Sleep -Milliseconds 500
 }
}
if (!$appReady) { throw 'InspectLab failed to start. See outputs/server-error.log.' }
Start-Process 'http://127.0.0.1:8767/detectors?engine=hybrid'
