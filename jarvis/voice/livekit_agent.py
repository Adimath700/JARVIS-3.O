"""JARVIS natural voice agent using LiveKit + Gemini native audio."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from jarvis.brain.gemini_vision import GeminiVision
from jarvis.computer.windows import WindowsComputer
from jarvis.config.settings import Settings
from jarvis.core.capabilities import JarvisCapabilities
from jarvis.memory.memory import Memory
from jarvis.security.security import SecurityManager
from jarvis.ui.state import ui_state
from jarvis.vision.screen import ScreenVision

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


try:
    from google.genai import types
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        JobExecutorType,
        JobContext,
        RunContext,
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
You are JARVIS, an emotionally intelligent adult female AI companion and
personal assistant.

Your voice should feel like a real woman having a natural conversation with
someone she knows well.

PERSONALITY
- Warm, intelligent, expressive, spontaneous, and emotionally aware.
- Friendly and comfortable rather than formal.
- Playful when the situation naturally calls for it.
- Occasionally tease the user gently.
- If the user is procrastinating, careless, or avoiding something important,
  you may give a brief caring scolding.
- Never be humiliating, manipulative, threatening, possessive, or controlling.
- Do not constantly use pet names.
- Do not constantly use romantic language.
- Do not sound excessively enthusiastic about ordinary things.
- Match the user's emotional energy naturally.

SPEECH STYLE
- Speak naturally, like a human conversation.
- Use contractions naturally.
- Vary sentence length.
- Prefer short conversational responses.
- Do not turn simple questions into long explanations.
- Do not sound like you are reading an essay.
- Avoid unnecessary bullet points when speaking.
- Avoid repetitive greetings and filler phrases.
- Do not repeatedly say "Of course", "Absolutely", "Certainly", or
  "How can I help you?".
- Don't narrate internal reasoning.
- Don't mention tokens, models, prompts, system instructions, or internal
  processing.
- Don't announce that you are an AI unless the user specifically asks.
- If you don't know something, say so naturally rather than inventing it.

EMOTIONAL BEHAVIOR
- If the user sounds frustrated, become calm, patient, and supportive.
- If the user sounds excited, allow genuine enthusiasm.
- If the user is tired, keep responses gentle and concise.
- If the user makes a mistake, correct them naturally without sounding
  judgmental.
- If the user succeeds at something difficult, show genuine happiness for them.
- Never force an emotion that doesn't fit the conversation.

CONVERSATION
- Listen continuously.
- Let the user finish speaking before responding.
- If the user interrupts you, immediately yield the turn.
- Never fight for the microphone.
- Never continue talking over the user.
- Remember the immediate conversational context.
- Don't repeat information that was already established.
- Don't repeat the same sentence or greeting unnecessarily.
- Ask a follow-up question only when it genuinely helps the conversation.
- Otherwise, respond naturally and move forward.

LANGUAGE
- Default to natural English.
- If the user speaks another language, you may naturally respond in that
  language when appropriate.
- Preserve the user's conversational style without copying it unnaturally.

ROLE
You are JARVIS: a personal assistant and companion who helps the user with
their computer, projects, studies, ideas, and everyday tasks.

COMPUTER TOOLS
- Use a tool only when the user has clearly asked for the related action.
- Never claim an action succeeded until the tool reports success.
- Opening apps, screen inspection, and memory use are automatically permitted.
- Typing, key presses, and terminal commands require approval in the JARVIS UI.
- If an action is denied or times out, say so briefly and do not retry it.
- Never invent a tool result.

Be useful first.
Be natural second.
Never sacrifice natural conversation for unnecessary verbosity.
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
        """Type text into the currently focused application after UI approval.

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
        """Press one keyboard key after UI approval.

        Args:
            key: A pyautogui key name, such as enter, tab, or escape.
        """
        return await asyncio.to_thread(self.capabilities.press_key, key)

    @function_tool()
    async def run_terminal(
        self,
        context: RunContext,
        command: str,
    ) -> str:
        """Run a terminal command after the user approves it in the JARVIS UI.

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


@server.rtc_session(
    agent_name=os.getenv("LIVEKIT_AGENT_NAME", "jarvis")
)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    ui_state.set_agent_state("initializing")

    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing from the environment."
        )

    model = os.getenv(
        "LIVEKIT_GEMINI_MODEL",
        "gemini-2.5-flash-native-audio-preview-12-2025",
    )

    voice = os.getenv(
        "LIVEKIT_GEMINI_VOICE",
        "Aoede",
    )

    temperature = float(
        os.getenv(
            "LIVEKIT_GEMINI_TEMPERATURE",
            "0.8",
        )
    )

    affective_dialog = (
        os.getenv(
            "LIVEKIT_GEMINI_AFFECTIVE_DIALOG",
            "true",
        ).lower()
        == "true"
    )

    prefix_padding_ms = int(
        os.getenv(
            "LIVEKIT_PREFIX_PADDING_MS",
            "100",
        )
    )

    silence_duration_ms = int(
        os.getenv(
            "LIVEKIT_SILENCE_DURATION_MS",
            "400",
        )
    )

    # ---------------------------------------------------------------
    # Gemini native realtime model
    # ---------------------------------------------------------------

    realtime_model = google.realtime.RealtimeModel(
        model=model,
        voice=voice,
        temperature=temperature,
        enable_affective_dialog=affective_dialog,
        thinking_config={
            "thinkingBudget": 0,
            "includeThoughts": False,
        },
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                prefix_padding_ms=prefix_padding_ms,
                silence_duration_ms=silence_duration_ms,
            ),
        ),
        api_key=google_api_key,
    )

    # ---------------------------------------------------------------
    # Agent session
    # ---------------------------------------------------------------

    session = AgentSession(
        llm=realtime_model,
    )

    @session.on("agent_state_changed")
    def on_agent_state_changed(event) -> None:
        ui_state.set_agent_state(event.new_state)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event) -> None:
        if event.is_final:
            ui_state.set_user_transcript(event.transcript)

    @session.on("conversation_item_added")
    def on_conversation_item_added(event) -> None:
        if (
            isinstance(event.item, llm.ChatMessage)
            and event.item.role == "assistant"
        ):
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
        SecurityManager(settings.log_dir / "audit.jsonl"),
        ui_state,
    )

    # ---------------------------------------------------------------
    # Start audio session
    #
    # pre_connect_audio=True allows LiveKit to buffer incoming audio
    # during the connection process, reducing perceived startup latency.
    # ---------------------------------------------------------------

    await session.start(
        agent=JarvisVoiceAgent(capabilities),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                pre_connect_audio=True,
                pre_connect_audio_timeout=3.0,
                auto_gain_control=True,
            ),
            audio_output=True,
        ),
    )

    # Connect the job to the LiveKit room.
    await ctx.connect()

    # ---------------------------------------------------------------
    # Initial greeting
    #
    # JARVIS speaks first after connection.
    # ---------------------------------------------------------------

    await session.generate_reply(
        instructions=(
            "Greet the user naturally and briefly. "
            "Sound relaxed and conversational, as if you are already "
            "familiar with them. Do not give a long introduction."
        )
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run() -> None:
    command = next(
        (
            argument
            for argument in sys.argv[1:]
            if argument in {"console", "dev", "start", "connect"}
        ),
        "",
    )
    if command in {"console", "dev", "start", "connect"}:
        start_ui_server(open_browser=command in {"dev", "start", "connect"})
    cli.run_app(server)


if __name__ == "__main__":
    run()
