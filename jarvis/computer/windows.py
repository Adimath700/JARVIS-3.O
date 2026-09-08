import json
import os
import shutil
import subprocess

try:
    import pyautogui
except ImportError:
    pyautogui = None


class WindowsComputer:
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
        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout[-6000:]

    def type_text(self, text):
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed")
        pyautogui.write(text, interval=0.01)
        return "Text typed."

    def press(self, key):
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed")
        pyautogui.press(key)
        return f"Pressed {key}."
