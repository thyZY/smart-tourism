param(
    [switch]$Lan
)

$ErrorActionPreference = 'Stop'

$listenHost = if ($Lan) { '0.0.0.0' } else { 'localhost' }
if ($Lan) {
    Write-Host 'LAN mode: open this app from a phone on the same reachable network using this PC IPv4 address on port 5173.'
    Write-Host 'Windows Firewall or network isolation may need to allow inbound TCP 5173.'
} else {
    Write-Host 'Local mode: open http://localhost:5173'
}

Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    & npm.cmd run dev -- --host $listenHost --port 5173 --strictPort
} finally {
    Pop-Location
}
