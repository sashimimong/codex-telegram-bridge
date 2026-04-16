$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
  py -3.11 -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev]"

Write-Host ""
Write-Host "Starting Codex Telegram Bridge on http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

& $python -m codex_telegram_bridge.main --host 127.0.0.1 --port 8765
