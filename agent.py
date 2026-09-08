"""Conventional LiveKit CLI entrypoint for the JARVIS voice agent."""

from jarvis.voice.livekit_agent import cli, server


if __name__ == "__main__":
    cli.run_app(server)
