from jarvis.config.settings import Settings
from jarvis.brain.ollama import OllamaBrain
from jarvis.brain.gemini_vision import GeminiVision
from jarvis.computer.windows import WindowsComputer
from jarvis.core.jarvis import Jarvis
from jarvis.memory.memory import Memory
from jarvis.security.security import SecurityManager
from jarvis.vision.screen import ScreenVision


def main():
    s = Settings()
    s.ensure_dirs()
    j = Jarvis(
        OllamaBrain(
            s.ollama_base_url,
            s.ollama_model,
            s.ollama_think,
            s.ollama_keep_alive,
            s.ollama_num_predict,
        ),
        Memory(s.memory_file),
        ScreenVision(s.screen_dir),
        GeminiVision(s.google_api_key, s.gemini_vision_model),
        WindowsComputer(),
        SecurityManager(s.log_dir / "audit.jsonl"),
    )
    print("\n=== JARVIS Python ===\nType /help for commands. Type /exit to quit.\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"/exit", "exit", "quit"}:
            break
        if text.lower() == "/help":
            print(
                "/screen /memory <text> /memories <query> /open <app> /type <text> /terminal <cmd> /status /exit"
            )
            continue
        if text.lower() == "/screen":
            text = "what is on my screen"
        elif text.lower().startswith("/memory "):
            text = "remember " + text[8:]
        elif text.lower().startswith("/memories "):
            text = "what do you remember about " + text[10:]
        elif text.lower().startswith("/open "):
            text = "open " + text[6:]
        elif text.lower().startswith("/type "):
            text = "type " + text[6:]
        elif text.lower().startswith("/terminal "):
            text = "run terminal " + text[10:]
        elif text.lower() == "/status":
            print("Ollama:", j.brain.available(), "Screen:", j.vision.active_window())
            continue
        try:
            print("JARVIS:", j.chat(text))
        except Exception as e:
            print("JARVIS error:", e)


if __name__ == "__main__":
    main()
