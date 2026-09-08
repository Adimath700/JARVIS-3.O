"""JARVIS natural voice agent using LiveKit + Gemini native audio."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


try:
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        JobContext,
        cli,
        room_io,
    )
    from livekit.plugins import google
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

Be useful first.
Be natural second.
Never sacrifice natural conversation for unnecessary verbosity.
""".strip()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class JarvisVoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=JARVIS_INSTRUCTIONS,
        )


# ---------------------------------------------------------------------------
# LiveKit server
# ---------------------------------------------------------------------------

server = AgentServer()


@server.rtc_session(
    agent_name=os.getenv("LIVEKIT_AGENT_NAME", "jarvis")
)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

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

    # ---------------------------------------------------------------
    # Gemini native realtime model
    # ---------------------------------------------------------------

    realtime_model = google.beta.realtime.RealtimeModel(
        model=model,
        voice=voice,
        temperature=temperature,
        enable_affective_dialog=affective_dialog,
        thinking_config={
            "thinkingBudget": 0,
            "includeThoughts": False,
        },
        api_key=google_api_key,
    )

    # ---------------------------------------------------------------
    # Agent session
    # ---------------------------------------------------------------

    session = AgentSession(
        llm=realtime_model,
    )

    # ---------------------------------------------------------------
    # Start audio session
    #
    # pre_connect_audio=True allows LiveKit to buffer incoming audio
    # during the connection process, reducing perceived startup latency.
    # ---------------------------------------------------------------

    await session.start(
        agent=JarvisVoiceAgent(),
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

if __name__ == "__main__":
    cli.run_app(server)