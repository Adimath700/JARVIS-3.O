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

    def _open_whatsapp_chat(self, phone_number, message=""):
        self._require_windows()
        phone = re.sub(r"\D", "", phone_number)
        if not 7 <= len(phone) <= 15:
            raise ValueError(
                "Use a full international phone number with 7 to 15 digits"
            )
        encoded = quote(message)
        desktop_url = f"whatsapp://send?phone={phone}"
        web_url = f"https://web.whatsapp.com/send?phone={phone}"
        if message:
            desktop_url += f"&text={encoded}"
            web_url += f"&text={encoded}"
        try:
            os.startfile(desktop_url)
        except OSError:
            webbrowser.open(web_url)
        timeout = float(os.getenv("JARVIS_WHATSAPP_LOAD_SECONDS", "10"))
        ready = self._wait_for_window("whatsapp", timeout)
        return phone, ready

    def send_whatsapp_message(self, phone_number, message):
        self._require_input()
        if not message.strip():
            raise ValueError("WhatsApp message cannot be empty")
        phone, ready = self._open_whatsapp_chat(phone_number, message)
        if not ready:
            return (
                f"Opened the WhatsApp chat for {phone}, but did not send because "
                "the WhatsApp window was not ready."
            )
        time.sleep(0.75)
        pyautogui.press("enter")
        return f"Submitted the WhatsApp message to {phone}."

    def start_whatsapp_call(self, phone_number, video=False):
        self._require_input()
        phone, ready = self._open_whatsapp_chat(phone_number)
        call_type = "video" if video else "voice"
        if not ready:
            return (
                f"Opened the WhatsApp chat for {phone}, but could not start the "
                f"{call_type} call because the WhatsApp window was not ready."
            )
        if Application is None or win32gui is None:
            return (
                f"Opened the WhatsApp chat for {phone}, but automatic calling "
                "requires pywinauto and pywin32."
            )
        handle = win32gui.GetForegroundWindow()
        try:
            window = Application(backend="uia").connect(handle=handle).window(
                handle=handle
            )
        except Exception:
            return (
                f"Opened the WhatsApp chat for {phone}, but could not inspect "
                f"the window to start the {call_type} call."
            )
        expected = f"{call_type} call"
        for button in window.descendants(control_type="Button"):
            label = button.window_text().strip().lower()
            if expected in label:
                button.click_input()
                return f"Started a WhatsApp {call_type} call with {phone}."
        return (
            f"Opened the WhatsApp chat for {phone}, but could not find the "
            f"{call_type} call button. Start it manually from the open chat."
        )
