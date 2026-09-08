$ErrorActionPreference='Stop'

if (-not $env:GOOGLE_API_KEY) { Write-Host 'GOOGLE_API_KEY is missing from the environment/.env'; exit 1 }
if (-not $env:LIVEKIT_URL) { Write-Host 'LIVEKIT_URL is missing from the environment/.env'; exit 1 }
if (-not $env:LIVEKIT_API_KEY) { Write-Host 'LIVEKIT_API_KEY is missing from the environment/.env'; exit 1 }
if (-not $env:LIVEKIT_API_SECRET) { Write-Host 'LIVEKIT_API_SECRET is missing from the environment/.env'; exit 1 }

python -m jarvis.voice.livekit_agent
