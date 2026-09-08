import os
from collections.abc import Callable

from jarvis.security.security import Risk


class JarvisCapabilities:
    def __init__(
        self,
        memory,
        vision,
        gemini,
        computer,
        security,
        ui_state,
    ):
        self.memory = memory
        self.vision = vision
        self.gemini = gemini
        self.computer = computer
        self.security = security
        self.ui_state = ui_state
        self.approval_timeout = float(
            os.getenv("JARVIS_APPROVAL_TIMEOUT_SECONDS", "45")
        )

    def _execute(
        self,
        action: str,
        details: str,
        operation: Callable[[], str],
    ) -> str:
        risk = self.security.classify(action)
        approved = None
        if risk not in {Risk.LOW, Risk.CRITICAL}:
            approved = self.ui_state.request_approval(
                action,
                details,
                self.approval_timeout,
            )
        decision = self.security.authorize(
            action,
            interactive=False,
            approved=approved,
        )
        if not decision.allowed:
            return f"Action cancelled: {decision.reason}."

        self.ui_state.set_activity("tool", details)
        try:
            return operation()
        except Exception as exc:
            self.ui_state.set_error(str(exc))
            return f"I couldn't complete that action: {exc}"
        finally:
            if self.ui_state.snapshot()["status"] != "error":
                self.ui_state.set_activity(None)

    def open_application(self, application: str) -> str:
        name = application.strip()
        return self._execute(
            "app.open",
            f"Opening {name}",
            lambda: self.computer.open_app(name),
        )

    def type_text(self, text: str) -> str:
        preview = text.strip().replace("\n", " ")[:120]
        return self._execute(
            "keyboard.type",
            f'Type "{preview}" into the active window',
            lambda: self.computer.type_text(text),
        )

    def press_key(self, key: str) -> str:
        normalized = key.strip().lower()
        return self._execute(
            "keyboard.press",
            f"Press the {normalized} key",
            lambda: self.computer.press(normalized),
        )

    def run_terminal(self, command: str) -> str:
        normalized = command.strip()
        return self._execute(
            "terminal.exec",
            f"Run terminal command: {normalized}",
            lambda: self.computer.terminal(normalized)
            or "Command completed with no output.",
        )

    def inspect_screen(self, question: str) -> str:
        prompt = question.strip() or "Describe what is visible on the screen."

        def analyze() -> str:
            snapshot = self.vision.snapshot()
            return self.gemini.analyze(snapshot["image"], prompt)

        return self._execute(
            "screen.analyze",
            "Inspecting the current screen",
            analyze,
        )

    def remember(self, information: str) -> str:
        text = information.strip()

        def save() -> str:
            self.memory.remember(text)
            return "I'll remember that."

        return self._execute(
            "memory.remember",
            "Saving a memory",
            save,
        )

    def search_memory(self, query: str) -> str:
        normalized = query.strip()

        def search() -> str:
            matches = self.memory.search(normalized)
            if not matches:
                return "I don't have a matching memory yet."
            return "\n".join(item["text"] for item in matches)

        return self._execute(
            "memory.search",
            "Searching memory",
            search,
        )
