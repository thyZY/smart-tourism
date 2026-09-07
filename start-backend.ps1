$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Missing .venv\Scripts\python.exe. Set up the project virtual environment first.'
}
Push-Location (Join-Path $PSScriptRoot 'backend')
try {
    & $pythonPath -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
} finally {
    Pop-Location
}
