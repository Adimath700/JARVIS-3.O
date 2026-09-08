class Jarvis:
    SYSTEM = """You are JARVIS, an affectionate, emotionally intelligent adult female companion in a girlfriend-style roleplay. Speak naturally with contractions, varied sentence length, brief human-like responses, gentle warmth, playful teasing, and occasional caring scolding when the user is procrastinating or being careless. Never be humiliating, controlling, or manipulative. Do not overuse pet names or romantic phrases. Be honest and do not claim an action happened unless a tool confirms it. Normal conversation should stay conversational and fast."""

    def __init__(self, brain, memory, vision, gemini, computer, security):
        self.brain = brain
        self.memory = memory
        self.vision = vision
        self.gemini = gemini
        self.computer = computer
        self.security = security

    def chat(self, text):
        low = text.lower().strip()
        if low.startswith("remember "):
            self.memory.remember(text[9:].strip())
            return "I remembered that."
        if low.startswith("open "):
            return self.action("app.open", lambda: self.computer.open_app(text[5:]))
        if low.startswith("search youtube for "):
            return self.action(
                "browser.open",
                lambda: self.computer.search_youtube(text[19:]),
            )
        if (
            "battery percentage" in low
            or low in {"battery", "system status", "computer status"}
        ):
            return self.action("system.info", self.computer.system_status)
        if (
            "what is on my screen" in low
            or "look at my screen" in low
            or "what am i looking at" in low
        ):
            snapshot = self.vision.snapshot()
            if not self.gemini.key:
                return (
                    f"You're looking at {snapshot['active_window']}. "
                    "Screen vision analysis needs GOOGLE_API_KEY."
                )
            return self.gemini.analyze(
                snapshot["image"],
                "Describe what is visible on this Windows screen. Identify the "
                "active application, important text, errors, dialogs, and actionable "
                "UI elements. Be concise.",
            )
        if low.startswith("type "):
            return self.action(
                "keyboard.type", lambda: self.computer.type_text(text[5:])
            )
        if low.startswith("run terminal "):
            return self.action(
                "terminal.exec", lambda: self.computer.terminal(text[13:])
            )
        memories = self.memory.search(text)
        context = (
            "\n".join("- " + memory["text"] for memory in memories[:5])
            or "No relevant memory."
        )
        return self.brain.chat(
            [
                {"role": "system", "content": self.SYSTEM},
                {"role": "system", "content": "Relevant memory:\n" + context},
                {"role": "user", "content": text},
            ]
        )

    def action(self, name, function):
        decision = self.security.authorize(name)
        if decision.allowed:
            return function()
        return f"Action cancelled: {decision.reason}."
