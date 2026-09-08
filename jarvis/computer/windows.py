import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote, quote_plus

import psutil

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

    def __init__(self):
        self._cached_whatsapp_handle = None
        self._cached_whatsapp_window = None

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

    @staticmethod
    def _wait_until(predicate, timeout: float, interval: float = 0.25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = predicate()
                if result:
                    return result
            except Exception:
                pass
            time.sleep(interval)
        return None

    def _matching_window_handle(self, title: str):
        if win32gui is None:
            return None
        expected = title.casefold()
        active = win32gui.GetForegroundWindow()
        if expected in win32gui.GetWindowText(active).casefold():
            return active
        matches = []

        def collect(handle, results):
            text = win32gui.GetWindowText(handle)
            if win32gui.IsWindowVisible(handle) and expected in text.casefold():
                results.append(handle)

        win32gui.EnumWindows(collect, matches)
        return matches[0] if matches else None

    def _wait_for_window(self, title: str, timeout: float):
        return self._wait_until(
            lambda: self._matching_window_handle(title),
            timeout,
        ) is not None

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
        if name.lower() == "whatsapp":
            return (
                "Opened WhatsApp and confirmed its controls are ready."
                if self._launch_whatsapp()
                else "Started WhatsApp, but its controls did not become ready."
            )
        if name.lower() == "spotify":
            return (
                "Opened Spotify and confirmed its window is ready."
                if self._launch_spotify()
                else "Started Spotify, but its window did not become ready."
            )
        timeout = float(os.getenv("JARVIS_APP_LOAD_SECONDS", "15"))
        app_id = self._start_menu_app_id(display)
        if app_id:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if self._wait_for_window(display, timeout):
                return f"Opened {display} and confirmed its window is ready."
            return (
                f"Started {display}, but no matching window appeared within "
                f"{timeout:g} seconds."
            )
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
                if self._wait_for_window(display, timeout):
                    return f"Opened {display} and confirmed its window is ready."
                return (
                    f"Started {display}, but no matching window appeared within "
                    f"{timeout:g} seconds."
                )
        except Exception:
            pass
        try:
            os.startfile(exe)
            if self._wait_for_window(display, timeout):
                return f"Opened {display} and confirmed its window is ready."
            return (
                f"Started {display}, but no matching window appeared within "
                f"{timeout:g} seconds."
            )
        except Exception:
            return f"I could not find {display} in the Windows Start Apps catalog."

    @staticmethod
    def _browser_executable(browser):
        requested = browser.strip().casefold()
        aliases = {
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "brave": "brave.exe",
            "brave browser": "brave.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
        }
        executable = aliases.get(requested)
        if executable is None:
            return None
        discovered = shutil.which(executable)
        if discovered:
            return discovered
        local = os.getenv("LOCALAPPDATA", "")
        program_files = os.getenv("PROGRAMFILES", "")
        program_files_x86 = os.getenv("PROGRAMFILES(X86)", "")
        candidates = {
            "chrome.exe": (
                Path(program_files) / "Google/Chrome/Application/chrome.exe",
                Path(program_files_x86) / "Google/Chrome/Application/chrome.exe",
                Path(local) / "Google/Chrome/Application/chrome.exe",
            ),
            "brave.exe": (
                Path(program_files)
                / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(program_files_x86)
                / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(local)
                / "BraveSoftware/Brave-Browser/Application/brave.exe",
            ),
            "msedge.exe": (
                Path(program_files_x86)
                / "Microsoft/Edge/Application/msedge.exe",
                Path(program_files) / "Microsoft/Edge/Application/msedge.exe",
            ),
        }
        return next(
            (
                str(candidate)
                for candidate in candidates[executable]
                if candidate.is_file()
            ),
            None,
        )

    def search_youtube(self, query, browser=""):
        self._require_windows()
        terms = query.strip()
        if not terms:
            raise ValueError("A YouTube search query is required")
        url = (
            "https://www.youtube.com/results?search_query="
            f"{quote_plus(terms)}"
        )
        requested_browser = browser.strip()
        if requested_browser:
            executable = self._browser_executable(requested_browser)
            if executable is None:
                return f"I could not find {requested_browser} on this PC."
            subprocess.Popen([executable, url])
        else:
            os.startfile(url)
        timeout = float(os.getenv("JARVIS_BROWSER_LOAD_SECONDS", "20"))
        if self._wait_for_window("youtube", timeout):
            destination = requested_browser or "the default browser"
            return (
                f'Searched YouTube for "{terms}" in {destination} and '
                "confirmed the page loaded."
            )
        return (
            f'Opened the YouTube search for "{terms}", but the page did not '
            f"visibly finish loading within {timeout:g} seconds."
        )

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

    def system_status(self):
        memory = psutil.virtual_memory()
        drive = Path.home().anchor or str(Path.home())
        disk = psutil.disk_usage(drive)
        battery = psutil.sensors_battery()
        if battery is None:
            battery_status = "Battery information is unavailable"
        else:
            power = "plugged in" if battery.power_plugged else "on battery"
            battery_status = f"Battery {battery.percent:.0f}% ({power})"
        active = self.active_window_title() or "unavailable"
        return (
            f"{battery_status}; CPU {psutil.cpu_percent(interval=0.1):.0f}%; "
            f"memory {memory.percent:.0f}%; disk {disk.percent:.0f}% used; "
            f"active window: {active}."
        )

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
        return f"Sent a {normalized} click at {x}, {y}."

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
        timeout = float(os.getenv("JARVIS_WHATSAPP_LOAD_SECONDS", "10"))
        if self._matching_window_handle("whatsapp") is None:
            self._start_search_and_open("WhatsApp", timeout)
        if self._wait_for_whatsapp_ready(timeout):
            return True
        app_id = self._start_menu_app_id("WhatsApp")
        if app_id:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return self._wait_for_whatsapp_ready(timeout) is not None
        return False

    def _whatsapp_window(self):
        if win32gui is None:
            return None
        handle = self._matching_window_handle("whatsapp")
        if handle is None:
            self._cached_whatsapp_handle = None
            self._cached_whatsapp_window = None
            return None
        if (
            handle == self._cached_whatsapp_handle
            and self._cached_whatsapp_window is not None
        ):
            return self._cached_whatsapp_window
        if Desktop is not None:
            try:
                window = Desktop(backend="uia").window(handle=handle)
                self._cached_whatsapp_handle = handle
                self._cached_whatsapp_window = window
                return window
            except Exception:
                pass
        if Application is None:
            return None
        try:
            window = Application(backend="uia").connect(handle=handle).window(
                handle=handle
            )
            self._cached_whatsapp_handle = handle
            self._cached_whatsapp_window = window
            return window
        except Exception:
            return None

    def _whatsapp_ready(self, require_chat=False):
        window = self._whatsapp_window()
        if window is None:
            return None
        if self._whatsapp_message_box(window) is not None:
            return window
        if require_chat:
            return None
        for control in self._window_controls(window, ("Edit", "Document")):
            label = self._control_label(control).casefold()
            if "search" in label or "new chat" in label:
                return window
        return None

    def _wait_for_whatsapp_ready(self, timeout, require_chat=False):
        return self._wait_until(
            lambda: self._whatsapp_ready(require_chat),
            timeout,
        )

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
        try:
            automation_id = control.element_info.automation_id
            if isinstance(automation_id, str):
                automation_id = automation_id.strip()
                if automation_id and automation_id not in labels:
                    labels.append(automation_id)
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
        expected = set(control_types)
        try:
            descendants = window.descendants()
            controls = []
            typed = False
            for control in descendants:
                try:
                    control_type = control.element_info.control_type
                    typed = True
                except Exception:
                    continue
                if control_type in expected:
                    controls.append(control)
            if typed or not descendants:
                return controls
        except Exception:
            pass
        controls = []
        for control_type in control_types:
            try:
                controls.extend(window.descendants(control_type=control_type))
            except Exception:
                pass
        return controls

    def _whatsapp_message_box(self, window):
        for control in self._window_controls(
            window,
            ("Edit", "Document"),
        ):
            label = self._control_label(control).casefold()
            if (
                any(
                    term in label
                    for term in ("type a message", "compose", "message to")
                )
                and "search" not in label
            ):
                return control
        return None

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
        timeout = float(os.getenv("JARVIS_WHATSAPP_CONTROL_SECONDS", "12"))
        search_timeout = float(
            os.getenv("JARVIS_WHATSAPP_SEARCH_SECONDS", "2.5")
        )
        chat_timeout = float(
            os.getenv("JARVIS_WHATSAPP_CHAT_SECONDS", "6")
        )

        def find_search():
            window = self._whatsapp_window()
            for control in self._window_controls(
                window,
                ("Edit", "Document"),
            ):
                label = self._control_label(control).casefold()
                if "search" in label or "new chat" in label:
                    return control
            return None

        search = self._wait_until(find_search, min(timeout, search_timeout))
        if search is not None and self._click_control(search):
            pyautogui.hotkey("ctrl", "a")
            self._paste_text(contact)
            target = contact.casefold()

            def select_match():
                window = self._whatsapp_window()
                for control in self._window_controls(
                    window,
                    ("ListItem", "Button", "Text"),
                ):
                    normalized = self._control_label(control).casefold()
                    try:
                        is_list_item = (
                            control.element_info.control_type == "ListItem"
                        )
                    except Exception:
                        is_list_item = False
                    if is_list_item and not normalized:
                        normalized = self._control_text(control).casefold()
                    if normalized == target or normalized.startswith(
                        f"{target}\n"
                    ):
                        return self._click_control(control)
                return False

            selected = bool(
                self._wait_until(select_match, search_timeout)
            )
            if not selected:
                pyautogui.press("down")
                pyautogui.press("enter")
            if self._wait_for_whatsapp_ready(
                chat_timeout,
                require_chat=True,
            ):
                return True

        pyautogui.hotkey("ctrl", "n")
        fallback_search = self._wait_until(
            find_search,
            min(search_timeout, 2),
        )
        if fallback_search is not None:
            self._click_control(fallback_search)
        self._paste_text(contact)
        time.sleep(0.25)
        pyautogui.press("down")
        pyautogui.press("enter")
        return (
            self._wait_for_whatsapp_ready(
                chat_timeout,
                require_chat=True,
            )
            is not None
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
        ready = (
            self._wait_for_whatsapp_ready(timeout, require_chat=True)
            is not None
        )
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
        if win32gui is not None:
            matches = []

            def collect(handle, results):
                title = win32gui.GetWindowText(handle).casefold()
                if (
                    win32gui.IsWindowVisible(handle)
                    and "whatsapp" in title
                    and "call" in title
                ):
                    results.append(handle)

            win32gui.EnumWindows(collect, matches)
            if matches:
                return True
        window = self._whatsapp_window()
        return self._find_whatsapp_action(
            window,
            ("end call", "hang up", "leave call"),
        ) is not None

    def wait_for_whatsapp_call(self, timeout=5):
        return self._wait_until(self._whatsapp_call_started, timeout) is not None

    def start_whatsapp_call(self, recipient, video=False):
        self._require_input()
        target, ready, _ = self._open_whatsapp_conversation(recipient)
        call_type = "video" if video else "voice"
        if not ready:
            return (
                f"Opened WhatsApp for {target}, but could not start the "
                f"{call_type} call because a matching chat was not ready."
            )
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
        control_timeout = float(
            os.getenv("JARVIS_WHATSAPP_CALL_BUTTON_SECONDS", "2")
        )
        confirm_timeout = float(
            os.getenv("JARVIS_WHATSAPP_CALL_CONFIRM_SECONDS", "4")
        )

        def click_call_control():
            window = self._whatsapp_window()
            call_button = self._find_whatsapp_action(
                window,
                terms,
                excluded,
            )
            if call_button is None:
                return False
            return self._click_control(call_button)

        triggered = self._wait_until(
            click_call_control,
            control_timeout,
        )
        if triggered:
            if self.wait_for_whatsapp_call(confirm_timeout):
                return f"Started a WhatsApp {call_type} call with {target}."
            return (
                f"Clicked the WhatsApp {call_type} call control for {target}, "
                "but no call window appeared, so the call is not confirmed."
            )
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
