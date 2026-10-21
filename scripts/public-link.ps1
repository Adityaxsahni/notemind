# Starts NoteMind with a free public HTTPS link (Cloudflare quick tunnel) and prints the link.
# Run it again whenever the link stops working: quick tunnels don't survive sleep or network
# changes, and every restart gets a new address. See docs/DEPLOY.md.
#
#   powershell -ExecutionPolicy Bypass -File scripts\public-link.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$compose = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.tunnel.yml")

Write-Host "Starting NoteMind and a fresh tunnel..."
& docker @compose up -d | Out-Null
& docker @compose up -d --force-recreate tunnel | Out-Null

$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep -Seconds 2
    $logs = & docker @compose logs tunnel 2>&1 | Out-String
    $match = [regex]::Matches($logs, "https://[a-z0-9-]+\.trycloudflare\.com") | Select-Object -Last 1
    if ($match) { $url = $match.Value }
}
if (-not $url) { throw "The tunnel didn't start. Is Docker Desktop running and the internet up?" }

Write-Host "Waiting for the app to answer..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        if ((Invoke-WebRequest "$url/health" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200) { break }
    } catch { Start-Sleep -Seconds 3 }
}

Write-Host ""
Write-Host "NoteMind is online at: $url" -ForegroundColor Green
Write-Host "It stays up while this computer and Docker Desktop are on."
