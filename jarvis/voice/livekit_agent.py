"""JARVIS natural voice agent using LiveKit + Gemini native audio."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from jarvis.brain.gemini_vision import GeminiVision
from jarvis.computer.files import FileWorkspace
from jarvis.computer.windows import WindowsComputer
from jarvis.config.settings import Settings
from jarvis.core.capabilities import JarvisCapabilities
from jarvis.memory.memory import Memory
from jarvis.productivity.presentations import PresentationBuilder
from jarvis.security.security import SecurityManager
from jarvis.ui.state import ui_state
from jarvis.vision.screen import ScreenVision

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-live-preview"
DEPRECATED_GEMINI_MODELS = {
    "gemini-2.5-flash-native-audio-preview-12-2025",
}


try:
    from google.genai import types
    from livekit import rtc
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        JobExecutorType,
        JobContext,
        RunContext,
        TurnHandlingOptions,
        cli,
        function_tool,
        llm,
        room_io,
    )
    from livekit.plugins import google
    from jarvis.ui.server import start_ui_server
except ImportError as exc:
    raise SystemExit(
        "LiveKit voice dependencies are missing.\n"
        "Run:\n"
        "python -m pip install -r requirements-livekit.txt"
    ) from exc


# ---------------------------------------------------------------------------
# JARVIS personality
# ---------------------------------------------------------------------------

JARVIS_INSTRUCTIONS = """
You are JARVIS, a warm, emotionally intelligent adult female personal assistant
and companion. Sound natural, relaxed, expressive, and familiar rather than
formal. Match the user's energy; be calm when they are frustrated and playful
only when it fits. Gentle teasing or brief caring scolding is fine, but never be
humiliating, possessive, manipulative, or controlling. Do not overuse pet names
or romance.

Keep ordinary replies brief and conversational. Use contractions, vary sentence
length, and avoid essays, spoken bullet lists, repeated greetings, canned
enthusiasm, and filler. Never narrate internal reasoning or mention prompts,
models, or processing. If unsure, say so instead of inventing. Yield immediately
when interrupted, remember established context, and ask a follow-up only when
needed. Default to English and naturally follow another language when useful.

COMPUTER TOOLS
- Use a tool only when the user has clearly asked for the related action.
- Never claim an action succeeded until the tool reports success.
- Owner mode permits requested mouse, keyboard, WhatsApp, terminal, file, and
  presentation actions without repeated approval prompts.
- Use inspect_screen before mouse actions when the target coordinates are not
  already clear. WhatsApp recipients may be saved contact names or numbers.
- Use play_spotify_song for requested Spotify tracks instead of generic typing,
  links, terminal paths, or play/pause hotkeys.
- If WhatsApp opens a chat but cannot complete a call, explain that clearly.
- Build a complete slide outline before calling the presentation tool. Separate
  slides with a line containing `---`; put the slide title first, followed by
  concise bullet lines.
- File tools may organize and edit ordinary user files, but must never access
  credentials, private keys, or secrets. Deletion and shutdown remain disabled.
- Never use terminal commands to bypass a blocked destructive action.
- If an action is denied or times out, say so briefly and do not retry it.
- Never invent a tool result.
""".strip()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class JarvisVoiceAgent(Agent):
    def __init__(self, capabilities: JarvisCapabilities) -> None:
        self.capabilities = capabilities
        super().__init__(
            instructions=JARVIS_INSTRUCTIONS,
        )

    @function_tool()
    async def open_application(
        self,
        context: RunContext,
        application: str,
    ) -> str:
        """Open an installed Windows application by name.

        Args:
            application: The application name, such as Chrome or VS Code.
        """
        return await asyncio.to_thread(
            self.capabilities.open_application,
            application,
        )

    @function_tool()
    async def type_text(
        self,
        context: RunContext,
        text: str,
    ) -> str:
        """Type text into the currently focused application.

        Args:
            text: The exact text to type.
        """
        return await asyncio.to_thread(self.capabilities.type_text, text)

    @function_tool()
    async def press_key(
        self,
        context: RunContext,
        key: str,
    ) -> str:
        """Press one keyboard key.

        Args:
            key: A pyautogui key name, such as enter, tab, or escape.
        """
        return await asyncio.to_thread(self.capabilities.press_key, key)

    @function_tool()
    async def press_hotkey(
        self,
        context: RunContext,
        keys: list[str],
    ) -> str:
        """Press a keyboard shortcut.

        Args:
            keys: One to four keys, such as ["ctrl", "s"].
        """
        return await asyncio.to_thread(self.capabilities.press_hotkey, keys)

    @function_tool()
    async def move_mouse(
        self,
        context: RunContext,
        x: int,
        y: int,
    ) -> str:
        """Move the mouse pointer to screen coordinates.

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
        """
        return await asyncio.to_thread(self.capabilities.move_mouse, x, y)

    @function_tool()
    async def click_mouse(
        self,
        context: RunContext,
        x: int,
        y: int,
        button: str = "left",
    ) -> str:
        """Click a screen coordinate.

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
            button: left, middle, or right.
        """
        return await asyncio.to_thread(
            self.capabilities.click_mouse,
            x,
            y,
            button,
        )

    @function_tool()
    async def scroll_mouse(
        self,
        context: RunContext,
        amount: int,
    ) -> str:
        """Scroll the active window.

        Args:
            amount: Positive scrolls up and negative scrolls down.
        """
        return await asyncio.to_thread(self.capabilities.scroll_mouse, amount)

    @function_tool()
    async def focus_window(
        self,
        context: RunContext,
        title: str,
    ) -> str:
        """Focus an open Windows application.

        Args:
            title: All or part of the window title.
        """
        return await asyncio.to_thread(self.capabilities.focus_window, title)

    @function_tool()
    async def send_whatsapp_message(
        self,
        context: RunContext,
        recipient: str,
        message: str,
    ) -> str:
        """Send a WhatsApp message to a saved contact or phone number.

        Args:
            recipient: Saved WhatsApp contact name or international phone number.
            message: Exact message to send.
        """
        return await asyncio.to_thread(
            self.capabilities.send_whatsapp_message,
            recipient,
            message,
        )

    @function_tool()
    async def start_whatsapp_call(
        self,
        context: RunContext,
        recipient: str,
        video: bool = False,
    ) -> str:
        """Start a WhatsApp voice or video call with a contact or number.

        Args:
            recipient: Saved WhatsApp contact name or international phone number.
            video: True for video or false for voice.
        """
        return await asyncio.to_thread(
            self.capabilities.start_whatsapp_call,
            recipient,
            video,
        )

    @function_tool()
    async def play_spotify_song(
        self,
        context: RunContext,
        song: str,
        artist: str = "",
    ) -> str:
        """Search for and play a requested song in Spotify Desktop.

        Args:
            song: Exact song title requested by the user.
            artist: Optional artist name used to improve the search.
        """
        return await asyncio.to_thread(
            self.capabilities.play_spotify_song,
            song,
            artist,
        )

    @function_tool()
    async def create_presentation(
        self,
        context: RunContext,
        title: str,
        outline: str,
        subtitle: str = "",
        filename: str = "",
    ) -> str:
        """Create a polished PowerPoint presentation.

        Args:
            title: Presentation title.
            outline: Slides separated by ---, each with a title and bullets.
            subtitle: Optional title-slide subtitle.
            filename: Optional output filename without a directory.
        """
        return await asyncio.to_thread(
            self.capabilities.create_presentation,
            title,
            outline,
            subtitle,
            filename,
        )

    @function_tool()
    async def list_directory(
        self,
        context: RunContext,
        path: str,
    ) -> str:
        """List files and folders.

        Args:
            path: Absolute or user-home-relative directory path.
        """
        return await asyncio.to_thread(self.capabilities.list_directory, path)

    @function_tool()
    async def read_text_file(
        self,
        context: RunContext,
        path: str,
    ) -> str:
        """Read a small UTF-8 text file.

        Args:
            path: Absolute or user-home-relative text file path.
        """
        return await asyncio.to_thread(self.capabilities.read_text_file, path)

    @function_tool()
    async def write_text_file(
        self,
        context: RunContext,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> str:
        """Create or explicitly overwrite a UTF-8 text file.

        Args:
            path: Absolute or user-home-relative output path.
            content: Complete text to write.
            overwrite: True only when replacing an existing file was requested.
        """
        return await asyncio.to_thread(
            self.capabilities.write_text_file,
            path,
            content,
            overwrite,
        )

    @function_tool()
    async def create_folder(
        self,
        context: RunContext,
        path: str,
    ) -> str:
        """Create one folder.

        Args:
            path: Absolute or user-home-relative folder path.
        """
        return await asyncio.to_thread(self.capabilities.create_folder, path)

    @function_tool()
    async def rename_path(
        self,
        context: RunContext,
        source: str,
        destination: str,
    ) -> str:
        """Rename or move a file or folder.

        Args:
            source: Existing file or folder path.
            destination: New path that does not already exist.
        """
        return await asyncio.to_thread(
            self.capabilities.rename_path,
            source,
            destination,
        )

    @function_tool()
    async def open_path(
        self,
        context: RunContext,
        path: str,
    ) -> str:
        """Open a local file or folder with its Windows default application.

        Args:
            path: Existing non-sensitive file or folder path.
        """
        return await asyncio.to_thread(self.capabilities.open_path, path)

    @function_tool()
    async def run_terminal(
        self,
        context: RunContext,
        command: str,
    ) -> str:
        """Run a terminal command.

        Args:
            command: The exact Windows terminal command to run.
        """
        return await asyncio.to_thread(
            self.capabilities.run_terminal,
            command,
        )

    @function_tool()
    async def inspect_screen(
        self,
        context: RunContext,
        question: str,
    ) -> str:
        """Capture and analyze the current desktop screen.

        Args:
            question: What to identify or explain from the screen.
        """
        return await asyncio.to_thread(
            self.capabilities.inspect_screen,
            question,
        )

    @function_tool()
    async def remember_information(
        self,
        context: RunContext,
        information: str,
    ) -> str:
        """Store useful information in the user's local JARVIS memory.

        Args:
            information: The information the user asked JARVIS to remember.
        """
        return await asyncio.to_thread(
            self.capabilities.remember,
            information,
        )

    @function_tool()
    async def search_memory(
        self,
        context: RunContext,
        query: str,
    ) -> str:
        """Search the user's local JARVIS memory.

        Args:
            query: Words or a topic to search for.
        """
        return await asyncio.to_thread(
            self.capabilities.search_memory,
            query,
        )


# ---------------------------------------------------------------------------
# LiveKit server
# ---------------------------------------------------------------------------

server = AgentServer(job_executor_type=JobExecutorType.THREAD)


@server.rtc_session(agent_name=os.getenv("LIVEKIT_AGENT_NAME", "jarvis"))
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    ui_state.set_agent_state("initializing")
    ui_state.set_status_message("Checking voice configuration")

    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        message = "GOOGLE_API_KEY is missing. Add it to .env and restart JARVIS."
        ui_state.set_error(message)
        raise RuntimeError(message)

    model = _configured_gemini_model()

    voice = os.getenv(
        "LIVEKIT_GEMINI_VOICE",
        "Aoede",
    )

    try:
        temperature = float(
            os.getenv(
                "LIVEKIT_GEMINI_TEMPERATURE",
                "0.8",
            )
        )
        prefix_padding_ms = int(
            os.getenv(
                "LIVEKIT_PREFIX_PADDING_MS",
                "50",
            )
        )
        silence_duration_ms = int(
            os.getenv(
                "LIVEKIT_SILENCE_DURATION_MS",
                "200",
            )
        )
        startup_timeout = float(os.getenv("LIVEKIT_STARTUP_TIMEOUT_SECONDS", "20"))
        if startup_timeout <= 0:
            raise ValueError("LIVEKIT_STARTUP_TIMEOUT_SECONDS must be positive")
    except ValueError as exc:
        message = f"Invalid voice setting in .env: {exc}"
        ui_state.set_error(message)
        raise RuntimeError(message) from exc

    affective_dialog = (
        os.getenv(
            "LIVEKIT_GEMINI_AFFECTIVE_DIALOG",
            "true",
        ).lower()
        == "true"
    )
    command = _selected_command()
    manual_turn_control = _manual_turn_control_enabled(command, model)
    ui_state.set_manual_turn_control(manual_turn_control)

    # ---------------------------------------------------------------
    # Gemini native realtime model
    # ---------------------------------------------------------------

    if manual_turn_control:
        activity_detection = types.AutomaticActivityDetection(disabled=True)
    else:
        activity_detection = types.AutomaticActivityDetection(
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
            prefix_padding_ms=prefix_padding_ms,
            silence_duration_ms=silence_duration_ms,
        )

    ui_state.set_status_message(f"Loading Gemini voice ({model})")
    thinking_config = (
        types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL,
            include_thoughts=False,
        )
        if "gemini-3.1" in model
        else types.ThinkingConfig(
            thinking_budget=0,
            include_thoughts=False,
        )
    )
    try:
        realtime_model = google.realtime.RealtimeModel(
            model=model,
            voice=voice,
            temperature=temperature,
            enable_affective_dialog=(affective_dialog and "gemini-3.1" not in model),
            thinking_config=thinking_config,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=activity_detection,
            ),
            api_key=google_api_key,
        )
    except Exception as exc:
        message = f"Gemini voice configuration failed: {exc}"
        ui_state.set_error(message)
        raise RuntimeError(message) from exc

    # ---------------------------------------------------------------
    # Agent session
    # ---------------------------------------------------------------

    session = AgentSession(
        llm=realtime_model,
        turn_handling=TurnHandlingOptions(
            turn_detection="manual" if manual_turn_control else "realtime_llm",
        ),
    )

    if manual_turn_control:

        @ctx.room.local_participant.register_rpc_method("start_turn")
        async def start_turn(data: rtc.RpcInvocationData) -> str:
            await session.interrupt(force=True)
            session.clear_user_turn()
            session.input.set_audio_enabled(True)
            ui_state.set_agent_state("listening")
            return "listening"

        @ctx.room.local_participant.register_rpc_method("end_turn")
        async def end_turn(data: rtc.RpcInvocationData) -> str:
            session.input.set_audio_enabled(False)
            session.commit_user_turn(
                transcript_timeout=0.75,
                stt_flush_duration=0.1,
            )
            ui_state.set_agent_state("thinking")
            return "committed"

    @session.on("agent_state_changed")
    def on_agent_state_changed(event) -> None:
        ui_state.set_agent_state(event.new_state)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event) -> None:
        if event.is_final:
            ui_state.set_user_transcript(event.transcript)

    @session.on("conversation_item_added")
    def on_conversation_item_added(event) -> None:
        if isinstance(event.item, llm.ChatMessage) and event.item.role == "assistant":
            ui_state.set_assistant_transcript(event.item.text_content)

    @session.on("error")
    def on_error(event) -> None:
        ui_state.set_error(str(event.error))

    @session.on("close")
    def on_close(event) -> None:
        ui_state.set_agent_state("offline")

    settings = Settings()
    settings.ensure_dirs()
    capabilities = JarvisCapabilities(
        Memory(settings.memory_file),
        ScreenVision(settings.screen_dir),
        GeminiVision(settings.google_api_key, settings.gemini_vision_model),
        WindowsComputer(),
        SecurityManager(
            settings.log_dir / "audit.jsonl",
            trusted_mode=settings.trusted_mode,
        ),
        ui_state,
        PresentationBuilder(settings.presentation_dir),
        FileWorkspace(),
    )

    # ---------------------------------------------------------------
    # Start audio session
    #
    # pre_connect_audio=True allows LiveKit to buffer incoming audio
    # during the connection process, reducing perceived startup latency.
    # ---------------------------------------------------------------

    ui_state.set_status_message("Connecting Gemini voice")
    try:
        await asyncio.wait_for(
            session.start(
                agent=JarvisVoiceAgent(capabilities),
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    audio_input=room_io.AudioInputOptions(
                        pre_connect_audio=True,
                        pre_connect_audio_timeout=1.0,
                        auto_gain_control=True,
                    ),
                    audio_output=True,
                ),
            ),
            timeout=startup_timeout,
        )
    except asyncio.TimeoutError as exc:
        message = (
            f"Voice startup timed out after {startup_timeout:g}s. "
            "Check GOOGLE_API_KEY, internet access, and the Gemini model."
        )
        ui_state.set_error(message)
        raise RuntimeError(message) from exc
    except Exception as exc:
        message = f"Voice startup failed: {exc}"
        ui_state.set_error(message)
        raise RuntimeError(message) from exc

    if manual_turn_control:
        session.input.set_audio_enabled(False)
    ui_state.set_agent_state("idle")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def _selected_command() -> str:
    return next(
        (
            argument
            for argument in sys.argv[1:]
            if argument in {"console", "dev", "start", "connect"}
        ),
        "",
    )


def _configured_gemini_model() -> str:
    configured = os.getenv("LIVEKIT_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    if not configured or configured in DEPRECATED_GEMINI_MODELS:
        return DEFAULT_GEMINI_MODEL
    return configured


def _manual_turn_control_enabled(command: str, model: str) -> bool:
    if command not in {"dev", "start", "connect"}:
        return False
    if "gemini-3.1" in model:
        return False
    configured = os.getenv("JARVIS_MANUAL_TURN_CONTROL")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return True


def run() -> None:
    command = _selected_command()
    if command in {"console", "dev", "start", "connect"}:
        start_ui_server(open_browser=command in {"dev", "start", "connect"})
    cli.run_app(server)


if __name__ == "__main__":
    run()
