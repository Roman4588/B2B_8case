$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (Get-Command docker -ErrorAction SilentlyContinue) { & docker compose down }
else {
    $linuxPath = '/mnt/' + $projectRoot.Substring(0,1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\','/')
    & wsl -d B2B8Case -u root --exec docker compose --project-directory $linuxPath -f "$linuxPath/docker-compose.yml" down
}
if ($LASTEXITCODE -ne 0) { throw 'Не удалось остановить стенд' }
