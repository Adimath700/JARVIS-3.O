import os
import time
from collections.abc import Callable


class JarvisCapabilities:
    def __init__(
        self,
        memory,
        vision,
        gemini,
        computer,
        security,
        ui_state,
        presentations=None,
        files=None,
    ):
        self.memory = memory
        self.vision = vision
        self.gemini = gemini
        self.computer = computer
        self.security = security
        self.ui_state = ui_state
        self.presentations = presentations
        self.files = files
        self.ui_state.set_trusted_mode(self.security.trusted_mode)
        self.approval_timeout = float(
            os.getenv("JARVIS_APPROVAL_TIMEOUT_SECONDS", "45")
        )

    def _execute(
        self,
        action: str,
        details: str,
        operation: Callable[[], str],
    ) -> str:
        approved = None
        if self.security.requires_approval(action):
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

    def search_youtube(self, query: str, browser: str = "") -> str:
        terms = query.strip()
        requested_browser = browser.strip()
        description = f'Search YouTube for "{terms}"'
        if requested_browser:
            description += f" in {requested_browser}"
        return self._execute(
            "browser.open",
            description,
            lambda: self.computer.search_youtube(
                terms,
                requested_browser,
            ),
        )

    def get_system_status(self) -> str:
        return self._execute(
            "system.info",
            "Reading battery and system status",
            self.computer.system_status,
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

    def press_hotkey(self, keys: list[str]) -> str:
        normalized = [key.strip().lower() for key in keys if key.strip()]
        return self._execute(
            "keyboard.hotkey",
            f"Press {' + '.join(normalized)}",
            lambda: self.computer.hotkey(normalized),
        )

    def move_mouse(self, x: int, y: int) -> str:
        return self._execute(
            "mouse.move",
            f"Move the pointer to {x}, {y}",
            lambda: self.computer.move_mouse(x, y),
        )

    def click_mouse(self, x: int, y: int, button: str = "left") -> str:
        normalized = button.strip().lower()
        return self._execute(
            "mouse.click",
            f"Click {normalized} at {x}, {y}",
            lambda: self.computer.click_mouse(x, y, normalized),
        )

    def _visible_target_location(self, target):
        snapshot = self.vision.snapshot(primary=True)
        location = self.gemini.locate(snapshot["image"], target)
        if location is None:
            return None
        minimum_confidence = float(
            os.getenv("JARVIS_VISUAL_MIN_CONFIDENCE", "0.55")
        )
        if location["confidence"] < minimum_confidence:
            return None
        x = snapshot["left"] + round(
            location["x"] * max(snapshot["width"] - 1, 0) / 1000
        )
        y = snapshot["top"] + round(
            location["y"] * max(snapshot["height"] - 1, 0) / 1000
        )
        return snapshot, location, x, y

    def click_visible_target(self, target: str) -> str:
        description = target.strip()
        if not description:
            raise ValueError("A visible click target is required")

        def click() -> str:
            grounded = self._visible_target_location(description)
            if grounded is None:
                return f'I could not see an enabled target matching "{description}".'
            before, location, x, y = grounded
            self.computer.click_mouse(x, y)
            threshold = float(
                os.getenv("JARVIS_VISUAL_CHANGE_THRESHOLD", "0.008")
            )
            timeout = float(
                os.getenv("JARVIS_VISUAL_CONFIRM_SECONDS", "3")
            )
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                time.sleep(0.25)
                after = self.vision.snapshot(primary=True)
                if (
                    self.vision.difference_ratio(
                        before["image"],
                        after["image"],
                    )
                    >= threshold
                ):
                    label = location["label"] or description
                    return (
                        f'Clicked "{label}" and confirmed a visible screen change.'
                    )
            return (
                f'Sent a click to "{description}", but the screen did not visibly '
                "change, so the action is not confirmed."
            )

        return self._execute(
            "mouse.click",
            f'Find and click visible target "{description}"',
            click,
        )

    def scroll_mouse(self, amount: int) -> str:
        return self._execute(
            "mouse.scroll",
            f"Scroll {amount} steps",
            lambda: self.computer.scroll_mouse(amount),
        )

    def focus_window(self, title: str) -> str:
        normalized = title.strip()
        return self._execute(
            "window.focus",
            f'Focus a window matching "{normalized}"',
            lambda: self.computer.focus_window(normalized),
        )

    def send_whatsapp_message(self, recipient: str, message: str) -> str:
        preview = message.strip().replace("\n", " ")[:140]
        return self._execute(
            "communication.send",
            f'Send WhatsApp message to {recipient}: "{preview}"',
            lambda: self.computer.send_whatsapp_message(recipient, message),
        )

    def start_whatsapp_call(
        self,
        recipient: str,
        video: bool = False,
    ) -> str:
        call_type = "video" if video else "voice"

        def start() -> str:
            result = self.computer.start_whatsapp_call(recipient, video)
            if result.startswith("Started "):
                return result
            target = (
                "WhatsApp video call camera button in the open chat header"
                if video
                else "WhatsApp voice call phone button in the open chat header"
            )
            try:
                grounded = self._visible_target_location(target)
            except Exception as exc:
                return f"{result} Visual fallback was unavailable: {exc}"
            if grounded is None:
                return f"{result} The button was also not visible in a fresh screenshot."
            _, _, x, y = grounded
            self.computer.click_mouse(x, y)
            if self.computer.wait_for_whatsapp_call(6):
                return (
                    f"Started a WhatsApp {call_type} call with {recipient} "
                    "and confirmed the call window."
                )
            return (
                f"Clicked the visible WhatsApp {call_type} call button for "
                f"{recipient}, but no call window appeared, so the call is "
                "not confirmed."
            )

        return self._execute(
            "communication.call",
            f"Start WhatsApp {call_type} call with {recipient}",
            start,
        )

    def play_spotify_song(self, song: str, artist: str = "") -> str:
        title = song.strip()
        performer = artist.strip()
        description = f'Play "{title}" on Spotify'
        if performer:
            description = f'Play "{title}" by {performer} on Spotify'
        return self._execute(
            "media.play",
            description,
            lambda: self.computer.play_spotify_song(title, performer),
        )

    def create_presentation(
        self,
        title: str,
        outline: str,
        subtitle: str = "",
        filename: str = "",
    ) -> str:
        if self.presentations is None:
            return "Presentation creation is not configured."
        slide_count = len(
            [
                section
                for section in outline.split("---")
                if section.strip()
            ]
        )

        def create() -> str:
            output = self.presentations.create(
                title,
                outline,
                subtitle,
                filename,
            )
            return f"Created the presentation at {output}."

        return self._execute(
            "file.write",
            f'Create a {slide_count + 1}-slide presentation titled "{title}"',
            create,
        )

    def list_directory(self, path: str) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized = path.strip()
        return self._execute(
            "file.list",
            f"List files in {normalized}",
            lambda: self.files.list_directory(normalized),
        )

    def read_text_file(self, path: str) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized = path.strip()
        return self._execute(
            "file.read",
            f"Read text file {normalized}",
            lambda: self.files.read_text(normalized),
        )

    def write_text_file(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized = path.strip()
        verb = "Overwrite" if overwrite else "Create"
        return self._execute(
            "file.write",
            f"{verb} text file {normalized}",
            lambda: self.files.write_text(normalized, content, overwrite),
        )

    def create_folder(self, path: str) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized = path.strip()
        return self._execute(
            "file.write",
            f"Create folder {normalized}",
            lambda: self.files.create_folder(normalized),
        )

    def rename_path(self, source: str, destination: str) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized_source = source.strip()
        normalized_destination = destination.strip()
        return self._execute(
            "file.rename",
            f"Rename {normalized_source} to {normalized_destination}",
            lambda: self.files.rename(
                normalized_source,
                normalized_destination,
            ),
        )

    def open_path(self, path: str) -> str:
        if self.files is None:
            return "File access is not configured."
        normalized = path.strip()
        return self._execute(
            "file.open",
            f"Open {normalized}",
            lambda: self.files.open_path(normalized),
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
