$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    & npm.cmd run dev -- --host localhost --port 5173 --strictPort
} finally {
    Pop-Location
}
