param([switch]$Background)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$composeArgs = @('compose','up','--build')
if ($Background) { $composeArgs += '-d' }
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker @composeArgs
} else {
    $linuxPath = '/mnt/' + $projectRoot.Substring(0,1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\','/')
    & wsl -d B2B8Case -u root --exec /bin/sh "$linuxPath/scripts/ensure-docker.sh"
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine не запустился. См. /var/log/docker.log внутри B2B8Case.' }
    $wslComposeArgs = @('compose','--project-directory',$linuxPath,'-f',"$linuxPath/docker-compose.yml",'up','--build')
    if ($Background) { $wslComposeArgs += '-d' }
    & wsl -d B2B8Case -u root --exec docker @wslComposeArgs
}
if ($LASTEXITCODE -ne 0) { throw 'Запуск завершился с ошибкой. Проверьте сообщения Docker выше.' }
Write-Host 'Интерфейс: http://localhost:8080. Войдите с личным email и паролем.'
Write-Host 'Первый запуск: powershell -ExecutionPolicy Bypass -File .\scripts\create-admin.ps1'
