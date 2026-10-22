param([string]$OutputDirectory = 'D:\B2B_8case-runtime\demo-audio')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$storyboard = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'demo\storyboard.json') | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$voice = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$voice.SelectVoice('Microsoft Irina Desktop')
$voice.Rate = 0
try {
    for ($index = 0; $index -lt $storyboard.Count; $index++) {
        $file = Join-Path $OutputDirectory ('{0:D2}.wav' -f $index)
        $voice.SetOutputToWaveFile($file)
        $escaped = [System.Security.SecurityElement]::Escape($storyboard[$index].text)
        $voice.SpeakSsml('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">' + $escaped + '<break time="2000ms"/></speak>')
        $voice.SetOutputToNull()
        Write-Host ('Narrated segment {0}: {1}' -f $index,$storyboard[$index].id)
    }
} finally { $voice.Dispose() }
