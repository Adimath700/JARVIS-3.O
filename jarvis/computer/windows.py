import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from urllib.parse import quote

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import win32gui
except ImportError:
    win32gui = None

try:
    from pywinauto import Application, Desktop
except ImportError:
    Application = None
    Desktop = None


class WindowsComputer:
    BLOCKED_TERMINAL_PATTERNS = (
        r"(^|[\s;&|])(del|erase|rd|rmdir|rm|ri|remove-item)(?=\s|$)",
        r"\b(shutdown|restart-computer|stop-computer|format|diskpart)\b",
        r"\b(os\.remove|os\.unlink|shutil\.rmtree)\b",
    )

    def _require_windows(self):
        if os.name != "nt":
            raise RuntimeError("This action is available only on Windows")

    def _require_input(self):
        self._require_windows()
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed")

    def active_window_title(self):
        if win32gui is None:
            return ""
        window = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(window)

    def _wait_for_window(self, title: str, timeout: float):
        deadline = time.monotonic() + timeout
        expected = title.lower()
        while time.monotonic() < deadline:
            if expected in self.active_window_title().lower():
                return True
            time.sleep(0.25)
        return False

    def _start_menu_app_id(self, query: str):
        if os.name != "nt":
            return None
        ps = "Get-StartApps | ConvertTo-Json -Compress"
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                text=True,
                timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            rows = json.loads(raw) if raw.strip() else []
            if isinstance(rows, dict):
                rows = [rows]
            query_lower = query.lower()
            exact = next(
                (
                    row
                    for row in rows
                    if str(row.get("Name", "")).lower() == query_lower
                ),
                None,
            )
            row = exact or next(
                (
                    row
                    for row in rows
                    if query_lower in str(row.get("Name", "")).lower()
                ),
                None,
            )
            return row.get("AppID") if row else None
        except Exception:
            return None

    def _start_search_and_open(self, application: str, timeout: float = 8.0) -> bool:
        self._require_input()
        pyautogui.press("win")
        time.sleep(0.3)
        pyautogui.write(application, interval=0.03)
        time.sleep(0.4)
        pyautogui.press("enter")
        return self._wait_for_window(application, timeout)

    def open_app(self, name):
        name = name.strip()
        aliases = {
            "vs code": "Visual Studio Code",
            "visual studio code": "Visual Studio Code",
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "notepad": "Notepad",
            "calculator": "Calculator",
            "whatsapp": "WhatsApp",
            "spotify": "Spotify",
            "discord": "Discord",
            "edge": "Microsoft Edge",
            "file explorer": "File Explorer",
        }
        display = aliases.get(name.lower(), name)
        if name.lower() in {"whatsapp", "spotify"} and self._start_search_and_open(
            display
        ):
            return f"Opening {display}."
        app_id = self._start_menu_app_id(display)
        if app_id:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return f"Opening {display}."
        exe_alias = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "file explorer": "explorer.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "vs code": "code.cmd",
            "visual studio code": "code.cmd",
        }
        exe = exe_alias.get(name.lower(), name)
        try:
            path = shutil.which(exe)
            if path:
                subprocess.Popen([path])
                return f"Opening {display}."
        except Exception:
            pass
        try:
            os.startfile(exe)
            return f"Opening {display}."
        except Exception:
            return f"I could not find {display} in the Windows Start Apps catalog."

    def terminal(self, command):
        normalized = command.strip()
        if any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self.BLOCKED_TERMINAL_PATTERNS
        ):
            raise PermissionError(
                "Destructive terminal commands are disabled; perform the action manually"
            )
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )[-6000:]
        if completed.returncode:
            return (
                f"Command exited with code {completed.returncode}."
                + (f"\n{output}" if output else "")
            )
        return output

    def type_text(self, text):
        self._require_input()
        pyautogui.write(text, interval=0.01)
        return "Text typed."

    def press(self, key):
        self._require_input()
        pyautogui.press(key)
        return f"Pressed {key}."

    def hotkey(self, keys):
        self._require_input()
        normalized = [key.strip().lower() for key in keys if key.strip()]
        if not normalized or len(normalized) > 4:
            raise ValueError("A hotkey must contain between one and four keys")
        pyautogui.hotkey(*normalized)
        return f"Pressed {' + '.join(normalized)}."

    def move_mouse(self, x, y):
        self._require_input()
        width, height = pyautogui.size()
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"Coordinates must fit the {width}x{height} screen")
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Moved the pointer to {x}, {y}."

    def click_mouse(self, x, y, button="left"):
        self._require_input()
        normalized = button.strip().lower()
        if normalized not in {"left", "middle", "right"}:
            raise ValueError("Mouse button must be left, middle, or right")
        width, height = pyautogui.size()
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"Coordinates must fit the {width}x{height} screen")
        pyautogui.click(x=x, y=y, button=normalized)
        return f"Clicked {normalized} at {x}, {y}."

    def scroll_mouse(self, amount):
        self._require_input()
        pyautogui.scroll(amount)
        return f"Scrolled {amount} steps."

    def focus_window(self, title):
        self._require_windows()
        if win32gui is None:
            raise RuntimeError("pywin32 is not installed")
        query = title.strip().lower()
        matches = []

        def collect(handle, results):
            text = win32gui.GetWindowText(handle)
            if win32gui.IsWindowVisible(handle) and query in text.lower():
                results.append((handle, text))

        win32gui.EnumWindows(collect, matches)
        if not matches:
            return f'I could not find an open window matching "{title}".'
        handle, matched_title = matches[0]
        win32gui.ShowWindow(handle, 9)
        win32gui.SetForegroundWindow(handle)
        return f"Focused {matched_title}."

    @staticmethod
    def _normalize_whatsapp_recipient(recipient):
        value = recipient.strip()
        if not value:
            raise ValueError("A WhatsApp contact name or phone number is required")
        if re.fullmatch(r"[\d+\s().-]+", value):
            phone = re.sub(r"\D", "", value)
            if not 7 <= len(phone) <= 15:
                raise ValueError(
                    "A WhatsApp phone number must contain 7 to 15 digits"
                )
            return phone, True
        return value, False

    def _launch_whatsapp(self):
        if "whatsapp" in self.active_window_title().lower():
            return True
        timeout = float(os.getenv("JARVIS_WHATSAPP_LOAD_SECONDS", "10"))
        if self._start_search_and_open("WhatsApp", timeout):
            return True
        app_id = self._start_menu_app_id("WhatsApp")
        if app_id:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return self._wait_for_window("whatsapp", timeout)
        return False

    def _whatsapp_window(self):
        if win32gui is None:
            return None
        handle = win32gui.GetForegroundWindow()
        if Desktop is not None:
            try:
                return Desktop(backend="uia").window(handle=handle)
            except Exception:
                pass
        if Application is None:
            return None
        try:
            return Application(backend="uia").connect(handle=handle).window(
                handle=handle
            )
        except Exception:
            return None

    @staticmethod
    def _control_label(control):
        labels = []
        try:
            text = control.window_text().strip()
            if text:
                labels.append(text)
        except Exception:
            pass
        try:
            name = control.element_info.name.strip()
            if name and name not in labels:
                labels.append(name)
        except Exception:
            pass
        return "\n".join(labels)

    def _control_text(self, control):
        labels = [self._control_label(control)]
        try:
            labels.extend(
                self._control_label(child)
                for child in control.descendants()
            )
        except Exception:
            pass
        return "\n".join(label for label in labels if label)

    @staticmethod
    def _click_control(control):
        try:
            control.click_input()
            return True
        except Exception:
            try:
                control.parent().click_input()
                return True
            except Exception:
                return False

    @staticmethod
    def _window_controls(window, control_types):
        if window is None:
            return []
        controls = []
        for control_type in control_types:
            try:
                controls.extend(window.descendants(control_type=control_type))
            except Exception:
                pass
        return controls

    def _whatsapp_message_box(self, window):
        return next(
            (
                control
                for control in self._window_controls(
                    window,
                    ("Edit", "Document"),
                )
                if any(
                    term in self._control_label(control).casefold()
                    for term in ("type a message", "compose", "message to")
                )
                and "search" not in self._control_label(control).casefold()
            ),
            None,
        )

    def _focus_whatsapp_composer(self, window):
        message_box = self._whatsapp_message_box(window)
        if message_box is not None and self._click_control(message_box):
            return True
        if window is None:
            return False
        try:
            bounds = window.rectangle()
            width = bounds.right - bounds.left
            pyautogui.click(
                x=bounds.left + int(width * 0.65),
                y=bounds.bottom - 55,
            )
            return True
        except Exception:
            return False

    def _find_whatsapp_action(self, window, terms, excluded_terms=()):
        for control in self._window_controls(
            window,
            ("Button", "Hyperlink", "Text"),
        ):
            label = self._control_label(control).casefold()
            if (
                label
                and any(term in label for term in terms)
                and not any(term in label for term in excluded_terms)
            ):
                return control
        return None

    def _whatsapp_message_count(self, window, message):
        expected = " ".join(message.casefold().split())
        if not expected:
            return 0
        matches = 0
        controls = self._window_controls(window, ("ListItem",))
        if not controls:
            controls = self._window_controls(window, ("Text",))
        for control in controls:
            label = " ".join(self._control_text(control).casefold().split())
            if expected in label:
                matches += 1
        return matches

    def _search_whatsapp_contact(self, contact):
        window = self._whatsapp_window()
        if window is not None:
            edits = self._window_controls(window, ("Edit",))
            search = next(
                (
                    edit
                    for edit in edits
                    if "search" in self._control_label(edit).lower()
                ),
                None,
            )
            if search is not None:
                self._click_control(search)
                pyautogui.hotkey("ctrl", "a")
                self._paste_text(contact)
                time.sleep(0.8)
                target = contact.casefold()
                for control in self._window_controls(
                    window,
                    ("ListItem", "Button", "Text"),
                ):
                    normalized = self._control_text(control).casefold()
                    if (
                        normalized == target
                        or normalized.startswith(f"{target}\n")
                    ) and self._click_control(control):
                        time.sleep(0.75)
                        return True

        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.35)
        self._paste_text(contact)
        time.sleep(0.8)
        pyautogui.press("down")
        pyautogui.press("enter")
        time.sleep(0.75)
        refreshed_window = self._whatsapp_window()
        return refreshed_window is None or self._focus_whatsapp_composer(
            refreshed_window
        )

    def _open_whatsapp_conversation(self, recipient, message=""):
        self._require_windows()
        normalized, is_phone = self._normalize_whatsapp_recipient(recipient)
        if not is_phone:
            ready = self._launch_whatsapp()
            if ready:
                ready = self._search_whatsapp_contact(normalized)
            return normalized, ready, False

        encoded = quote(message)
        desktop_url = f"whatsapp://send?phone={normalized}"
        web_url = f"https://web.whatsapp.com/send?phone={normalized}"
        if message:
            desktop_url += f"&text={encoded}"
            web_url += f"&text={encoded}"
        try:
            os.startfile(desktop_url)
        except OSError:
            webbrowser.open(web_url)
        timeout = float(os.getenv("JARVIS_WHATSAPP_LOAD_SECONDS", "10"))
        ready = self._wait_for_window("whatsapp", timeout)
        return normalized, ready, bool(message)

    def _paste_text(self, text):
        if pyperclip is None:
            pyautogui.write(text, interval=0.01)
            return
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = None
        try:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        finally:
            if previous is not None:
                time.sleep(0.25)
                pyperclip.copy(previous)

    def send_whatsapp_message(self, recipient, message):
        self._require_input()
        if not message.strip():
            raise ValueError("WhatsApp message cannot be empty")
        target, ready, message_prefilled = self._open_whatsapp_conversation(
            recipient,
            message,
        )
        if not ready:
            return (
                f"Opened WhatsApp for {target}, but did not send because a "
                "matching chat was not ready."
            )
        time.sleep(0.75)
        window = self._whatsapp_window()
        if not self._focus_whatsapp_composer(window):
            return (
                f"Opened the WhatsApp chat for {target}, but could not focus "
                "the message box."
            )
        previous_matches = self._whatsapp_message_count(window, message)
        if not message_prefilled:
            self._paste_text(message)
        pyautogui.press("enter")
        time.sleep(0.6)
        window = self._whatsapp_window()
        if self._whatsapp_message_count(window, message) > previous_matches:
            return f"Sent the WhatsApp message to {target}."
        send_button = self._find_whatsapp_action(
            window,
            ("send",),
            ("send voice", "send video", "send file"),
        )
        if send_button is not None and self._click_control(send_button):
            time.sleep(0.5)
            if (
                self._whatsapp_message_count(
                    self._whatsapp_window(),
                    message,
                )
                > previous_matches
            ):
                return f"Sent the WhatsApp message to {target}."
        return (
            f"Submitted the WhatsApp message to {target}, but WhatsApp did "
            "not expose delivery confirmation."
        )

    def _whatsapp_call_started(self):
        title = self.active_window_title().casefold()
        if "whatsapp" in title and "call" in title:
            return True
        window = self._whatsapp_window()
        return self._find_whatsapp_action(
            window,
            ("end call", "hang up", "leave call"),
        ) is not None

    def start_whatsapp_call(self, recipient, video=False):
        self._require_input()
        target, ready, _ = self._open_whatsapp_conversation(recipient)
        call_type = "video" if video else "voice"
        if not ready:
            return (
                f"Opened WhatsApp for {target}, but could not start the "
                f"{call_type} call because a matching chat was not ready."
            )
        window = self._whatsapp_window()
        terms = (
            ("video call", "start video", "video")
            if video
            else ("voice call", "audio call", "start call", "call")
        )
        excluded = (
            ("voice", "audio", "group", "turn off")
            if video
            else ("video", "group", "end call", "hang up")
        )
        call_button = self._find_whatsapp_action(window, terms, excluded)
        triggered = (
            call_button is not None and self._click_control(call_button)
        )
        if triggered:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if self._whatsapp_call_started():
                    return (
                        f"Started a WhatsApp {call_type} call with {target}."
                    )
                time.sleep(0.25)
        return (
            f"Opened the WhatsApp chat for {target}, but could not find or "
            f"confirm its {call_type} call control."
        )

    def play_spotify_song(self, song, artist=""):
        self._require_input()
        title = song.strip()
        performer = artist.strip()
        if not title:
            raise ValueError("A Spotify song name is required")
        if not self._launch_spotify():
            return "I could not open Spotify from the Windows Start menu."
        query = " ".join(part for part in (title, performer) if part)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.35)
        pyautogui.hotkey("ctrl", "a")
        self._paste_text(query)
        time.sleep(float(os.getenv("JARVIS_SPOTIFY_SEARCH_SECONDS", "1.2")))
        pyautogui.press("enter")
        deadline = time.monotonic() + float(
            os.getenv("JARVIS_SPOTIFY_CONFIRM_SECONDS", "3")
        )
        while time.monotonic() < deadline:
            if self._spotify_now_playing_matches(title):
                return f'Playing "{query}" on Spotify.'
            time.sleep(0.25)
        return f'Asked Spotify to play "{query}" from Quick Search.'

    def _launch_spotify(self):
        if "spotify" in self.active_window_title().casefold():
            return True
        timeout = float(os.getenv("JARVIS_SPOTIFY_LOAD_SECONDS", "10"))
        if self._start_search_and_open("Spotify", timeout):
            return True
        app_id = self._start_menu_app_id("Spotify")
        if app_id:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return self._wait_for_window("spotify", timeout)
        return False

    def _spotify_window(self):
        if win32gui is None:
            return None
        handle = win32gui.GetForegroundWindow()
        if Desktop is not None:
            try:
                return Desktop(backend="uia").window(handle=handle)
            except Exception:
                pass
        if Application is None:
            return None
        try:
            return Application(backend="uia").connect(handle=handle).window(
                handle=handle
            )
        except Exception:
            return None

    def _spotify_now_playing_matches(self, title):
        expected = " ".join(title.casefold().split())
        window = self._spotify_window()
        if not expected or window is None:
            return False
        try:
            window_bounds = window.rectangle()
            player_top = window_bounds.bottom - min(
                180,
                (window_bounds.bottom - window_bounds.top) // 3,
            )
        except Exception:
            return False
        for control in self._window_controls(window, ("Text", "Button")):
            label = " ".join(self._control_label(control).casefold().split())
            if expected not in label:
                continue
            try:
                if control.rectangle().top >= player_top:
                    return True
            except Exception:
                pass
        return False
