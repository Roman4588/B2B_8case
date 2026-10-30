﻿$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (Get-Command docker -ErrorAction SilentlyContinue) { & docker compose down }
else {
    throw 'Docker не найден. Проверьте установку Docker Desktop.'
}
if ($LASTEXITCODE -ne 0) { throw 'Не удалось остановить стенд' }
