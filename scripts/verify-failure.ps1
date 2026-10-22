param([string]$BaseUrl = 'http://localhost:18908')
$ErrorActionPreference = 'Stop'
$null = Invoke-RestMethod "$BaseUrl/api/auth/login" -Method Post -ContentType application/json -Body '{"password":"copilot-demo"}' -SessionVariable web
$before = Invoke-RestMethod "$BaseUrl/api/incidents?state=firing" -WebSession $web
$accepted = $before.items | Where-Object handling -eq 'accepted' | Select-Object -First 1
$sourcePreserved = $false
$recovered = $false
try {
    & wsl -d B2B8Case -u root -- docker stop b2b8case-clean-prometheus-1 | Out-Null
    & wsl -d B2B8Case -u root -- docker exec b2b8case-clean-worker-1 python -c 'from app.tasks import poll; poll.run()' | Out-Null
    $after = Invoke-RestMethod "$BaseUrl/api/incidents?state=firing" -WebSession $web
    $source = Invoke-RestMethod "$BaseUrl/api/sources" -WebSession $web
    $sourcePreserved = $before.total -eq $after.total -and [bool]$source.state.error
    if (-not $sourcePreserved) { throw 'Active events were lost or source error was hidden' }
} finally {
    & wsl -d B2B8Case -u root -- docker start b2b8case-clean-prometheus-1 | Out-Null
}
for ($attempt=0; $attempt -lt 10; $attempt++) {
    & wsl -d B2B8Case -u root -- docker exec b2b8case-clean-worker-1 python -c 'from app.tasks import poll; poll.run()' | Out-Null
    $source = Invoke-RestMethod "$BaseUrl/api/sources" -WebSession $web
    if (-not $source.state.error) { $recovered = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $recovered) { throw 'Source did not reconnect' }
& wsl -d B2B8Case -u root -- docker restart b2b8case-clean-api-1 b2b8case-clean-worker-1 | Out-Null
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try {
        $ready = Invoke-RestMethod "$BaseUrl/api/health/ready"
        if ($ready.status -eq 'ready') { break }
    } catch { }
    Start-Sleep -Seconds 2
}
$profile = Invoke-RestMethod "$BaseUrl/api/auth/me" -WebSession $web
if (-not $profile.id) { throw 'Profile or session was lost' }
$persistent = $true
if ($accepted) {
    $record = Invoke-RestMethod "$BaseUrl/api/incidents/$($accepted.id)" -WebSession $web
    $persistent = $record.handling -eq 'accepted'
}
if (-not $persistent) { throw 'Manual state was lost after restart' }
$report = [ordered]@{ source_failure_preserves_events=$sourcePreserved; source_reconnects=$recovered; session_survives_restart=$true; manual_state_survives_restart=$persistent; active_before=$before.total }
$report | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'docs\failure-report.json')
$report | ConvertTo-Json
