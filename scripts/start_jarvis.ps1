$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot\..
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.11 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python main.py
