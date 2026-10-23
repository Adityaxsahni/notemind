# Puts NoteMind online at its permanent Vercel address, with the backend running on this
# computer. Run it after every restart (or whenever the site stops answering):
#
#   powershell -ExecutionPolicy Bypass -File scripts\go-live.ps1
#
# What it does: starts Docker Desktop and the app, opens a free Cloudflare tunnel to it,
# points the Vercel website at the tunnel (BACKEND_URL + PROXY_SECRET), and redeploys the
# website. Visitors always use https://notemind-tau-two.vercel.app; only the hidden backend
# address changes. Needs the Vercel CLI login on this computer (`npx vercel login`, once).

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$site = "https://notemind-tau-two.vercel.app"
$vercel = @("--yes", "vercel@65.0.0")
$compose = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.tunnel.yml")

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

Step "Docker Desktop"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $exe = Get-ChildItem "$env:LOCALAPPDATA\Programs", "$env:ProgramFiles\Docker" -Recurse -Filter "Docker Desktop.exe" -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exe) { throw "Docker Desktop isn't installed." }
    Start-Process $exe.FullName
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep 4
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker Desktop didn't start. Restart the computer and run this again." }
}
Write-Host "running"

Step "NoteMind app and tunnel"
& docker @compose up -d --remove-orphans | Out-Null
& docker @compose up -d --force-recreate tunnel | Out-Null
$backend = $null
for ($i = 0; $i -lt 60 -and -not $backend; $i++) {
    Start-Sleep 2
    $logs = & docker @compose logs tunnel 2>&1 | Out-String
    $match = [regex]::Matches($logs, "https://[a-z0-9-]+\.trycloudflare\.com") | Select-Object -Last 1
    if ($match) { $backend = $match.Value }
}
if (-not $backend) { throw "The tunnel didn't start. Is the internet up?" }
for ($i = 0; $i -lt 90; $i++) {
    try { if ((Invoke-WebRequest "$backend/health" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200) { break } } catch { Start-Sleep 3 }
}
Write-Host "backend at $backend"

Step "Vercel settings"
$secret = (Select-String -Path ".env" -Pattern "^PROXY_SECRET=(.+)$").Matches[0].Groups[1].Value
$settings = [ordered]@{
    BACKEND_URL          = $backend
    PROXY_SECRET         = $secret
    NEXT_PUBLIC_SITE_URL = $site
    FORCE_HTTPS          = "true"
}
Push-Location frontend
foreach ($name in $settings.Keys) {
    npx @vercel env rm $name production --yes *> $null
    $settings[$name] | npx @vercel env add $name production *> $null
    Write-Host "set $name"
}

Step "Redeploying the website (about a minute)"
$latest = (npx @vercel ls notemind 2>$null | Select-String "https://notemind-[a-z0-9]+-adityaxsahni\.vercel\.app" | Select-Object -First 1).Matches[0].Value
npx @vercel redeploy $latest --target production *> $null
Pop-Location
for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest "$site/health" -UseBasicParsing -TimeoutSec 15).Content -match "ok") { break } } catch { }
    Start-Sleep 5
}

Write-Host ""
Write-Host "NoteMind is online at: $site" -ForegroundColor Green
Write-Host "It works while this computer is on with Docker Desktop running."
Write-Host "After a restart or sleep, run this script again (the link stays the same)."
