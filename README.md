# JARVIS Python Edition

A Windows-first, Python-native foundation for a personal AI desktop assistant.

## Included
- Local Ollama brain (Qwen3 by default)
- Optional Gemini vision for on-demand screen understanding
- Native Windows screen capture + active-window detection
- Local Whisper STT (`faster-whisper`)
- Local Piper TTS support (optional)
- Windows app launching, mouse, keyboard, files, terminal tools
- Security/risk gates and audit log
- Persistent JSON memory
- CLI assistant loop
- Optional LiveKit/Gemini Live voice adapter scaffold

## Important
This build is intentionally Python-only for the assistant runtime. The holographic web UI is not part of this core build; it can be attached later as a UI client.

## Quick start (Windows)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

Install Ollama separately and make sure `qwen3:8b` exists:
```powershell
ollama pull qwen3:8b
```

The default `.env.example` disables Qwen's thinking mode for normal assistant
conversation, keeps the model loaded for 30 minutes, and caps responses at 256
tokens. Adjust `OLLAMA_THINK`, `OLLAMA_KEEP_ALIVE`, and
`OLLAMA_NUM_PREDICT` if you prefer deeper or longer responses.

For screen vision, set `GOOGLE_API_KEY` in `.env`. The screenshot is captured locally and sent only when JARVIS is asked to inspect the screen.

For local STT, `faster-whisper` is used. For Piper TTS, install Piper separately and configure `PIPER_EXE` and `PIPER_VOICE`.

## Commands
Natural language examples:
- `Jarvis, what is on my screen?`
- `open WhatsApp`
- `open VS Code`
- `what time is it?`
- `remember that my project is JARVIS`
- `what do you remember about my project?`
- `type hello` (approval required)
- `run terminal dir` (approval required)
- `exit`

Direct CLI commands:
- `/screen`
- `/memory <text>`
- `/memories <query>`
- `/open <app>`
- `/type <text>`
- `/terminal <command>`
- `/status`
- `/exit`

## Security
The model never decides whether an action is safe. The security manager classifies actions and requires approval for medium/high/critical actions. Destructive terminal commands and file deletion are blocked by default.

## Natural Voice System

JARVIS uses LiveKit Agents with Gemini native audio for the natural voice path. The current voice configuration keeps Gemini 2.5 native audio because it supports affective dialogue, while screen vision can use a separate Gemini model.

Required `.env` values:

- `GOOGLE_API_KEY`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_AGENT_NAME=jarvis`
- `LIVEKIT_GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-12-2025`
- `LIVEKIT_GEMINI_VOICE=Aoede`
- `LIVEKIT_GEMINI_AFFECTIVE_DIALOG=true`
- `LIVEKIT_PREFIX_PADDING_MS=100`
- `LIVEKIT_SILENCE_DURATION_MS=400`

The LiveKit silence duration controls how quickly JARVIS responds after you
finish speaking. Increase it if natural pauses are being cut off.

Install the optional voice dependencies:

```powershell
python -m pip install -r requirements-livekit.txt
```

For local console testing, run the project launcher. It uses the Python
entrypoint directly, so it does not depend on the LiveKit CLI simulator:

```powershell
.\scripts\run_livekit_agent.ps1 -Mode console
```

Use `-Text` to start console mode without microphone input:

```powershell
.\scripts\run_livekit_agent.ps1 -Mode console -Text
```

To connect the agent to your LiveKit project, configure `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env`, then run:

```powershell
.\scripts\run_livekit_agent.ps1 -Mode dev
```

## LiveKit CLI

The repository now includes the conventional `agent.py` entrypoint, so the
official LiveKit CLI can run:

```powershell
lk agent console
```

On Windows, install or update the official CLI with:

```powershell
winget install LiveKit.LiveKitCLI
winget upgrade LiveKit.LiveKitCLI
```

If `lk` produces a Node.js `MODULE_NOT_FOUND` error, check which executable
PowerShell found:

```powershell
Get-Command lk | Format-List Source
```

If the source is under an npm directory, remove the unrelated npm package and
reinstall the official CLI:

```powershell
npm uninstall -g lk
winget install LiveKit.LiveKitCLI
```

You can always use `scripts\run_livekit_agent.ps1` while troubleshooting the
external CLI.
