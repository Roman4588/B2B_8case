param([switch]$ResetPassword)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$action = if ($ResetPassword) { 'reset-password' } else { 'create-admin' }
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker compose exec api python -m app.manage $action
} else {
    $linuxPath = '/mnt/' + $projectRoot.Substring(0,1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\','/')
    & wsl -d B2B8Case -u root --exec docker compose --project-directory $linuxPath exec api python -m app.manage $action
}
if ($LASTEXITCODE -ne 0) { throw 'Account was not saved. Check the message above.' }
