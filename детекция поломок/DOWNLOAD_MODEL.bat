@echo off
set "OLLAMA_HOST=127.0.0.1:11435"
set "OLLAMA_MODELS=%~dp0models"
set "OLLAMA_NO_CLOUD=1"
"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" pull qwen3-vl:4b-instruct
pause
