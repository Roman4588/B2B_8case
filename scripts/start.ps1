param([switch]$Background, [int]$ReadyTimeoutSeconds = 900)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Установите Docker Desktop с официального сайта, включите WSL 2 и перезагрузите компьютер. Затем повторите запуск.'
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path -LiteralPath $desktop) {
        Write-Host 'Запускаем Docker Desktop…'
        Start-Process -FilePath $desktop -WindowStyle Hidden
        $engineDeadline = (Get-Date).AddMinutes(3)
        do {
            Start-Sleep -Seconds 3
            & docker info *> $null
            if ($LASTEXITCODE -eq 0) { break }
        } while ((Get-Date) -lt $engineDeadline)
    }
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine недоступен. Откройте Docker Desktop и проверьте сообщение об ошибке WSL и свободное место на диске.' }
}
Write-Host 'Собираем и запускаем стенд. Первый запуск требует интернета и свободного места.'
& docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Сборка или запуск завершились ошибкой. Сообщение Docker находится выше.' }
$port = if ($env:APP_PORT) { $env:APP_PORT } else { '8080' }
if (-not $env:APP_PORT -and (Test-Path .env)) {
    $portLine = Get-Content .env | Where-Object { $_ -match '^APP_PORT=\d+$' } | Select-Object -Last 1
    if ($portLine) { $port = $portLine.Substring(9) }
}
$address = "http://localhost:$port"
Write-Host 'Контейнеры запущены. Ждём базу знаний и модель (первый запуск может занять несколько минут)…'
$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod "$address/api/health/ready" -TimeoutSec 5
        if ($health.status -eq 'ready') { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $ready) { throw 'Подготовка не завершена за отведённое время. Проверьте: docker compose logs --tail=100 worker api. Контейнеры оставлены работающими.' }
Write-Host "Готово: $address"
Write-Host 'Первый вход: powershell -ExecutionPolicy Bypass -File .\scripts\create-admin.ps1'
Write-Host 'Проверяющим: docs/reviewer-guide.md. Docker Desktop должен оставаться запущенным.'
if (-not $Background) { & docker compose logs -f --tail=20 }