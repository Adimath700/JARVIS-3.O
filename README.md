# JARVIS Python Edition

A Windows-first, Python-native foundation for a personal AI desktop assistant.

## Included
- Local Ollama brain (Qwen3 by default)
- Optional Gemini vision for on-demand screen understanding
- Native Windows screen capture + active-window detection
- Local Whisper STT (`faster-whisper`)
- Local Piper TTS support (optional)
- Windows app launching, mouse, keyboard, files, terminal tools
- WhatsApp message and call automation
- PowerPoint presentation generation with a polished dark theme
- Trusted owner mode, destructive-action safeguards, and audit log
- Persistent JSON memory
- CLI assistant loop
- LiveKit/Gemini native audio with secured computer-control tools
- Voice-reactive holographic web UI with hold-to-talk

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
conversation, preloads the model in the background, keeps it loaded for 30
minutes, uses a 2048-token context, and caps responses at 128 tokens. Adjust
`OLLAMA_THINK`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_NUM_CTX`, and
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
- `type hello`
- `run terminal dir`
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
The model never decides whether an action is safe. The security manager
classifies actions and writes every decision to the local audit log.
`JARVIS_TRUSTED_MODE=true` enables owner mode, so requested mouse, keyboard,
file, WhatsApp, presentation, and terminal actions run without repeated
confirmation. Set it to `false` to restore **Allow once / Deny** prompts.
Credential/key files are blocked, and destructive deletion, shutdown, and
restart actions remain disabled. Common destructive terminal commands are also
rejected rather than used to bypass those controls.

## Natural Voice + Holographic UI

JARVIS uses LiveKit Agents with Gemini native audio for the natural voice
path. The current voice configuration uses Gemini 3.1 Flash Live, while screen
vision can use a separate Gemini model. The voice agent can open applications,
understand the current screen, use local memory, and perform owner-authorized
laptop actions.

Required `.env` values:

- `GOOGLE_API_KEY`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_AGENT_NAME=jarvis`
- `LIVEKIT_GEMINI_MODEL=gemini-3.1-flash-live-preview`
- `LIVEKIT_GEMINI_VOICE=Aoede`
- `LIVEKIT_GEMINI_AFFECTIVE_DIALOG=false`
- `LIVEKIT_PREFIX_PADDING_MS=50`
- `LIVEKIT_SILENCE_DURATION_MS=200`
- `LIVEKIT_STARTUP_TIMEOUT_SECONDS=20`
- `JARVIS_MANUAL_TURN_CONTROL=false`
- `JARVIS_UI_PORT=8765`
- `JARVIS_UI_AUTO_OPEN=true`
- `JARVIS_TRUSTED_MODE=true`
- `JARVIS_APPROVAL_TIMEOUT_SECONDS=45`

The LiveKit silence duration controls how quickly JARVIS responds after you
finish speaking. The faster 200 ms default follows Gemini Live's supported
automatic VAD configuration. Increase it if natural pauses are being cut off.

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

The launcher starts the local UI server and opens the holographic interface at
`http://127.0.0.1:8765`. Click **Connect JARVIS** once, allow microphone access,
then hold the central control (or hold Space) while speaking. The UI responds
to listening, thinking, speaking, tool, approval, and error states. Agent audio
drives the core animation in real time.

Gemini 3.1 uses its low-latency automatic turn detector because its Live API
does not support LiveKit's manual `generate_reply()` flow. Legacy compatible
models may opt into `JARVIS_MANUAL_TURN_CONTROL=true`. Console mode always
keeps automatic turn detection.

The UI creates a unique LiveKit room for each connection and dispatches the
configured `LIVEKIT_AGENT_NAME` into it. Keep the `dev` process running while
using the interface.

Voice tool examples:

- “Open Visual Studio Code.”
- “What is visible on my screen?”
- “Remember that my project uses Python 3.11.”
- “Type this message into the active window.”
- “Press Enter.”
- “Run `dir` in the terminal.”
- “Send ‘I will arrive at six’ on WhatsApp to Priya.”
- “Start a WhatsApp video call with Mom.”
- “Create a five-slide presentation about renewable energy.”
- “List the files in my Documents folder.”
- “Open my project presentation.”

WhatsApp automation requires WhatsApp Desktop or WhatsApp Web to already be
signed in. JARVIS accepts a saved contact name or a complete international
number. For names, it opens WhatsApp through Windows Start search, searches the
signed-in account's contacts, and selects the matching result without fixed
screen coordinates. Calls use the accessible WhatsApp call button when
available; if the installed WhatsApp version does not expose that control,
JARVIS leaves the selected chat open for manual completion.

Generated presentations are stored in `data/presentations` by default. Change
`JARVIS_PRESENTATION_DIR` in `.env` to use another folder.

The UI server binds only to `127.0.0.1`. LiveKit credentials stay in the Python
process and the browser receives only a short-lived room participant token.

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
