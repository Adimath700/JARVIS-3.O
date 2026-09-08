param(
    [ValidateSet('console', 'dev', 'start')]
    [string]$Mode = 'console',
    [switch]$Text
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    Write-Error 'Virtual environment not found. Run the README setup commands first.'
}

$AgentArgs = @('-m', 'jarvis.voice.livekit_agent', $Mode)
if ($Mode -eq 'console' -and $Text) {
    $AgentArgs += '--text'
}

if ($Mode -in @('dev', 'start')) {
    Write-Host 'Starting JARVIS voice agent and holographic UI...'
}

& $Python @AgentArgs
exit $LASTEXITCODE
