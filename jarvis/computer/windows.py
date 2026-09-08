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
    from pywinauto import Application
except ImportError:
    Application = None


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
            "discord": "Discord",
            "edge": "Microsoft Edge",
            "file explorer": "File Explorer",
        }
        display = aliases.get(name.lower(), name)
        if name.lower() == "whatsapp" and self._start_search_and_open(display):
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
        if Application is None or win32gui is None:
            return None
        handle = win32gui.GetForegroundWindow()
        try:
            return Application(backend="uia").connect(handle=handle).window(
                handle=handle
            )
        except Exception:
            return None

    @staticmethod
    def _control_label(control):
        try:
            return control.window_text().strip()
        except Exception:
            return ""

    def _whatsapp_message_box(self, window):
        if window is None:
            return None
        return next(
            (
                edit
                for edit in window.descendants(control_type="Edit")
                if "message" in self._control_label(edit).lower()
                and "search" not in self._control_label(edit).lower()
            ),
            None,
        )

    def _search_whatsapp_contact(self, contact):
        window = self._whatsapp_window()
        if window is not None:
            edits = window.descendants(control_type="Edit")
            search = next(
                (
                    edit
                    for edit in edits
                    if "search" in self._control_label(edit).lower()
                ),
                None,
            )
            if search is not None:
                search.click_input()
                search.set_edit_text(contact)
                time.sleep(0.8)
                target = contact.casefold()
                for control_type in ("ListItem", "Button", "Text"):
                    for control in window.descendants(control_type=control_type):
                        label = self._control_label(control)
                        normalized = label.casefold()
                        if normalized == target or normalized.startswith(
                            f"{target}\n"
                        ):
                            control.click_input()
                            time.sleep(0.5)
                            return True

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        self._paste_text(contact)
        time.sleep(0.8)
        pyautogui.press("down")
        pyautogui.press("enter")
        time.sleep(0.5)
        refreshed_window = self._whatsapp_window()
        return (
            refreshed_window is None
            or self._whatsapp_message_box(refreshed_window) is not None
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
                time.sleep(0.1)
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
        if not message_prefilled:
            message_box = self._whatsapp_message_box(self._whatsapp_window())
            if message_box is not None:
                message_box.click_input()
            self._paste_text(message)
        pyautogui.press("enter")
        return f"Submitted the WhatsApp message to {target}."

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
        if window is None:
            return (
                f"Opened the WhatsApp chat for {target}, but automatic calling "
                "requires pywinauto and pywin32."
            )
        expected = f"{call_type} call"
        for button in window.descendants(control_type="Button"):
            label = self._control_label(button).lower()
            if expected in label:
                button.click_input()
                return f"Started a WhatsApp {call_type} call with {target}."
        return (
            f"Opened the WhatsApp chat for {target}, but could not find the "
            f"{call_type} call button. Start it manually from the open chat."
        )
