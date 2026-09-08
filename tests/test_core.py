import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from jarvis.brain.gemini_vision import GeminiVision
from jarvis.brain.ollama import OllamaBrain
from jarvis.computer.files import FileWorkspace
from jarvis.computer.windows import WindowsComputer
from jarvis.core.capabilities import JarvisCapabilities
from jarvis.memory.memory import Memory
from jarvis.productivity.presentations import PresentationBuilder
from jarvis.security.security import Risk, SecurityManager
from jarvis.ui.state import AssistantUiState


def test_security():
    log = Path(tempfile.mkdtemp()) / "a.log"
    s = SecurityManager(log)
    assert s.classify("screen.capture") == Risk.LOW
    assert s.classify("terminal.exec") == Risk.HIGH
    assert s.classify("communication.send") == Risk.HIGH
    assert s.classify("file.open") == Risk.HIGH
    assert s.classify("media.play") == Risk.LOW
    assert s.authorize(
        "keyboard.type",
        interactive=False,
        approved=True,
    ).allowed
    assert '"allowed": true' in log.read_text(encoding="utf-8")
    trusted = SecurityManager(log.parent / "trusted.log", trusted_mode=True)
    assert trusted.authorize("keyboard.type", interactive=False).allowed
    assert not trusted.authorize("system.shutdown", interactive=False).allowed


def test_memory():
    p = Path(tempfile.mkdtemp()) / "m.json"
    m = Memory(p)
    m.remember("JARVIS test")
    assert m.search("jarvis")


def test_ollama_latency_settings():
    response = Mock()
    response.json.return_value = {"message": {"content": "Hello"}}
    response.raise_for_status.return_value = None
    with patch("jarvis.brain.ollama.requests.post", return_value=response) as post:
        brain = OllamaBrain("http://localhost:11434", "qwen3:8b", False, "30m", 256)
        assert brain.chat([{"role": "user", "content": "Hi"}]) == "Hello"
    payload = post.call_args.kwargs["json"]
    assert payload["think"] is False
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_predict"] == 256
    assert payload["options"]["num_ctx"] == 2048


def test_ollama_warm_up():
    response = Mock()
    response.raise_for_status.return_value = None
    with patch("jarvis.brain.ollama.requests.post", return_value=response) as post:
        brain = OllamaBrain("http://localhost:11434", "qwen3:8b")
        assert brain.warm_up()
    assert post.call_args.kwargs["json"]["prompt"] == ""


def test_voice_capabilities_require_approval():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.type_text.return_value = "Text typed."
    approvals = Mock()
    approvals.request_approval.return_value = True
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        Mock(),
        Mock(),
        computer,
        SecurityManager(root / "audit.jsonl"),
        approvals,
    )

    assert capabilities.type_text("hello") == "Text typed."
    approvals.request_approval.assert_called_once()
    computer.type_text.assert_called_once_with("hello")


def test_voice_capabilities_honor_denial():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    approvals = Mock()
    approvals.request_approval.return_value = False
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        Mock(),
        Mock(),
        computer,
        SecurityManager(root / "audit.jsonl"),
        approvals,
    )

    assert capabilities.run_terminal("whoami") == "Action cancelled: user denied."
    computer.terminal.assert_not_called()


def test_voice_capabilities_trusted_mode_skips_approval():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.type_text.return_value = "Text typed."
    approvals = Mock()
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        Mock(),
        Mock(),
        computer,
        SecurityManager(root / "audit.jsonl", trusted_mode=True),
        approvals,
    )

    assert capabilities.type_text("hello") == "Text typed."
    approvals.request_approval.assert_not_called()
    approvals.set_trusted_mode.assert_called_once_with(True)


def test_gemini_locator_parses_grounded_coordinates():
    vision = GeminiVision("key", "model")
    with patch.object(
        vision,
        "analyze",
        return_value=(
            '```json\n{"found":true,"x":750,"y":125,'
            '"confidence":0.93,"label":"Video call"}\n```'
        ),
    ):
        assert vision.locate("screen.png", "video call button") == {
            "x": 750,
            "y": 125,
            "confidence": 0.93,
            "label": "Video call",
        }


def test_visible_target_click_maps_screen_and_confirms_change():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.click_mouse.return_value = "Sent a left click."
    vision = Mock()
    vision.snapshot.side_effect = (
        {
            "image": "before.png",
            "left": -100,
            "top": 20,
            "width": 2000,
            "height": 1000,
        },
        {
            "image": "after.png",
            "left": -100,
            "top": 20,
            "width": 2000,
            "height": 1000,
        },
    )
    vision.difference_ratio.return_value = 0.1
    gemini = Mock()
    gemini.locate.return_value = {
        "x": 750,
        "y": 125,
        "confidence": 0.93,
        "label": "Video call",
    }
    approvals = Mock()
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        vision,
        gemini,
        computer,
        SecurityManager(root / "audit.jsonl", trusted_mode=True),
        approvals,
    )
    with patch("jarvis.core.capabilities.time.sleep"):
        result = capabilities.click_visible_target(
            "WhatsApp video call button"
        )
    assert result == (
        'Clicked "Video call" and confirmed a visible screen change.'
    )
    computer.click_mouse.assert_called_once_with(1399, 145)


def test_whatsapp_requires_approval():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.send_whatsapp_message.return_value = "Message sent."
    approvals = Mock()
    approvals.request_approval.return_value = True
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        Mock(),
        Mock(),
        computer,
        SecurityManager(root / "audit.jsonl"),
        approvals,
    )

    result = capabilities.send_whatsapp_message("15551234567", "Hello")
    assert result == "Message sent."
    computer.send_whatsapp_message.assert_called_once_with("15551234567", "Hello")


def test_whatsapp_accepts_contact_names_and_phone_numbers():
    computer = WindowsComputer()
    assert computer._normalize_whatsapp_recipient("+1 (555) 123-4567") == (
        "15551234567",
        True,
    )
    assert computer._normalize_whatsapp_recipient("Priya Sharma") == (
        "Priya Sharma",
        False,
    )
    with (
        patch.object(computer, "_require_windows"),
        patch.object(computer, "_launch_whatsapp", return_value=True),
        patch.object(computer, "_search_whatsapp_contact", return_value=True) as search,
    ):
        assert computer._open_whatsapp_conversation("Priya Sharma") == (
            "Priya Sharma",
            True,
            False,
        )
    search.assert_called_once_with("Priya Sharma")


def test_whatsapp_message_focuses_composer_and_verifies_send():
    computer = WindowsComputer()
    input_driver = Mock()
    window = Mock()
    with (
        patch.object(computer, "_require_input"),
        patch.object(
            computer,
            "_open_whatsapp_conversation",
            return_value=("Priya", True, False),
        ),
        patch.object(computer, "_whatsapp_window", return_value=window),
        patch.object(computer, "_focus_whatsapp_composer", return_value=True),
        patch.object(computer, "_paste_text") as paste,
        patch.object(
            computer,
            "_whatsapp_message_count",
            side_effect=(0, 1),
        ),
        patch("jarvis.computer.windows.pyautogui", input_driver),
        patch("jarvis.computer.windows.time.sleep"),
    ):
        result = computer.send_whatsapp_message("Priya", "On my way")
    assert result == "Sent the WhatsApp message to Priya."
    paste.assert_called_once_with("On my way")
    input_driver.press.assert_called_once_with("enter")


def test_whatsapp_detects_modern_composer_and_video_labels():
    computer = WindowsComputer()
    search = Mock()
    search.window_text.return_value = "Search or start a new chat"
    search.element_info.name = ""
    composer = Mock()
    composer.window_text.return_value = "Type a message to Priya"
    composer.element_info.name = ""
    video = Mock()
    video.window_text.return_value = ""
    video.element_info.name = ""
    video.element_info.automation_id = "VideoCallButton"
    window = Mock()

    def descendants(*, control_type):
        return {
            "Edit": [search],
            "Document": [composer],
            "Button": [video],
            "Hyperlink": [],
            "Text": [],
        }.get(control_type, [])

    window.descendants.side_effect = descendants
    assert computer._whatsapp_message_box(window) is composer
    assert (
        computer._find_whatsapp_action(
            window,
            ("video call", "start video", "video"),
            ("voice", "audio", "group", "turn off"),
        )
        is video
    )


def test_whatsapp_control_lookup_scans_accessibility_tree_once():
    computer = WindowsComputer()
    edit = Mock()
    edit.element_info.control_type = "Edit"
    button = Mock()
    button.element_info.control_type = "Button"
    window = Mock()
    window.descendants.return_value = [edit, button]
    assert computer._window_controls(window, ("Button",)) == [button]
    window.descendants.assert_called_once_with()


def test_whatsapp_contact_search_uses_keyboard_fast_path():
    computer = WindowsComputer()
    search = Mock()
    input_driver = Mock()
    with (
        patch.object(
            computer,
            "_wait_until",
            side_effect=(search, None),
        ),
        patch.object(computer, "_click_control", return_value=True),
        patch.object(computer, "_paste_text") as paste,
        patch.object(
            computer,
            "_wait_for_whatsapp_ready",
            return_value=Mock(),
        ),
        patch("jarvis.computer.windows.pyautogui", input_driver),
    ):
        assert computer._search_whatsapp_contact("Priya") is True
    paste.assert_called_once_with("Priya")
    assert input_driver.press.call_args_list == [call("down"), call("enter")]
    assert call("ctrl", "n") not in input_driver.hotkey.call_args_list


def test_whatsapp_video_call_uses_accessible_button():
    computer = WindowsComputer()
    call_button = Mock()
    with (
        patch.object(computer, "_require_input"),
        patch.object(
            computer,
            "_open_whatsapp_conversation",
            return_value=("Priya", True, False),
        ),
        patch.object(computer, "_whatsapp_window", return_value=Mock()),
        patch.object(
            computer,
            "_find_whatsapp_action",
            return_value=call_button,
        ),
        patch.object(computer, "_click_control", return_value=True) as click,
        patch.object(computer, "_whatsapp_call_started", return_value=True),
    ):
        result = computer.start_whatsapp_call("Priya", video=True)
    assert result == "Started a WhatsApp video call with Priya."
    click.assert_called_once_with(call_button)


def test_whatsapp_call_uses_short_accessibility_fast_path():
    computer = WindowsComputer()
    with (
        patch.object(computer, "_require_input"),
        patch.object(
            computer,
            "_open_whatsapp_conversation",
            return_value=("Priya", True, False),
        ),
        patch.object(computer, "_wait_until", return_value=None) as wait,
    ):
        result = computer.start_whatsapp_call("Priya", video=True)
    assert "could not find or confirm its video call control" in result
    assert wait.call_args.args[1] == 2


def test_whatsapp_call_uses_visual_fallback_and_confirms_window():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.start_whatsapp_call.return_value = (
        "Opened the WhatsApp chat for Priya, but could not find or confirm "
        "its video call control."
    )
    computer.wait_for_whatsapp_call.return_value = True
    vision = Mock()
    vision.snapshot.return_value = {
        "image": "screen.png",
        "left": 0,
        "top": 0,
        "width": 1920,
        "height": 1080,
    }
    gemini = Mock()
    gemini.locate.return_value = {
        "x": 900,
        "y": 100,
        "confidence": 0.9,
        "label": "Video call",
    }
    approvals = Mock()
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        vision,
        gemini,
        computer,
        SecurityManager(root / "audit.jsonl", trusted_mode=True),
        approvals,
    )
    assert capabilities.start_whatsapp_call("Priya", video=True) == (
        "Started a WhatsApp video call with Priya and confirmed the call window."
    )
    computer.click_mouse.assert_called_once_with(1727, 108)
    computer.wait_for_whatsapp_call.assert_called_once_with(4)


def test_youtube_search_waits_for_loaded_page():
    computer = WindowsComputer()
    with (
        patch.object(computer, "_require_windows"),
        patch.object(
            computer,
            "_browser_executable",
            return_value="C:/Brave/brave.exe",
        ),
        patch.object(computer, "_wait_for_window", return_value=True) as wait,
        patch("jarvis.computer.windows.subprocess.Popen") as start,
    ):
        result = computer.search_youtube("LiveKit agents", "Brave")
    assert result == (
        'Searched YouTube for "LiveKit agents" in Brave and confirmed '
        "the page loaded."
    )
    start.assert_called_once_with(
        [
            "C:/Brave/brave.exe",
            "https://www.youtube.com/results?search_query=LiveKit+agents",
        ]
    )
    wait.assert_called_once_with("youtube", 20)


def test_system_status_reports_battery_and_usage():
    computer = WindowsComputer()
    battery = Mock(percent=78, power_plugged=True)
    with (
        patch("jarvis.computer.windows.psutil.sensors_battery", return_value=battery),
        patch(
            "jarvis.computer.windows.psutil.virtual_memory",
            return_value=Mock(percent=42),
        ),
        patch(
            "jarvis.computer.windows.psutil.disk_usage",
            return_value=Mock(percent=61),
        ),
        patch(
            "jarvis.computer.windows.psutil.cpu_percent",
            return_value=17,
        ),
        patch.object(computer, "active_window_title", return_value="WhatsApp"),
    ):
        assert computer.system_status() == (
            "Battery 78% (plugged in); CPU 17%; memory 42%; disk 61% used; "
            "active window: WhatsApp."
        )


def test_spotify_quick_search_selects_requested_song():
    computer = WindowsComputer()
    input_driver = Mock()
    with (
        patch.object(computer, "_require_input"),
        patch.object(computer, "_launch_spotify", return_value=True),
        patch.object(
            computer,
            "_spotify_now_playing_matches",
            return_value=True,
        ),
        patch.object(computer, "_paste_text") as paste,
        patch("jarvis.computer.windows.pyautogui", input_driver),
        patch("jarvis.computer.windows.time.sleep"),
    ):
        result = computer.play_spotify_song("Blinding Lights", "The Weeknd")
    assert result == 'Playing "Blinding Lights The Weeknd" on Spotify.'
    assert [entry.args for entry in input_driver.hotkey.call_args_list] == [
        ("ctrl", "k"),
        ("ctrl", "a"),
    ]
    paste.assert_called_once_with("Blinding Lights The Weeknd")
    input_driver.press.assert_called_once_with("enter")


def test_spotify_playback_confirmation_uses_now_playing_bar():
    computer = WindowsComputer()
    window = Mock()
    window.rectangle.return_value = Mock(
        left=0,
        top=0,
        right=1200,
        bottom=800,
    )
    search_result = Mock()
    search_result.window_text.return_value = "Blinding Lights"
    search_result.element_info.name = ""
    search_result.rectangle.return_value = Mock(top=240)
    now_playing = Mock()
    now_playing.window_text.return_value = "Blinding Lights"
    now_playing.element_info.name = ""
    now_playing.rectangle.return_value = Mock(top=740)
    window.descendants.side_effect = lambda *, control_type: (
        [search_result, now_playing] if control_type == "Text" else []
    )
    with patch.object(computer, "_spotify_window", return_value=window):
        assert computer._spotify_now_playing_matches("Blinding Lights")


def test_spotify_capability_uses_dedicated_media_action():
    root = Path(tempfile.mkdtemp())
    computer = Mock()
    computer.play_spotify_song.return_value = "Playing."
    approvals = Mock()
    approvals.snapshot.return_value = {"status": "idle"}
    capabilities = JarvisCapabilities(
        Memory(root / "memory.json"),
        Mock(),
        Mock(),
        computer,
        SecurityManager(root / "audit.jsonl"),
        approvals,
    )

    assert capabilities.play_spotify_song("Numb", "Linkin Park") == "Playing."
    computer.play_spotify_song.assert_called_once_with("Numb", "Linkin Park")
    approvals.request_approval.assert_not_called()


def test_windows_start_search_launch():
    computer = WindowsComputer()
    input_driver = Mock()
    with (
        patch("jarvis.computer.windows.os.name", "nt"),
        patch("jarvis.computer.windows.pyautogui", input_driver),
        patch.object(computer, "_wait_for_window", return_value=True) as wait,
        patch("jarvis.computer.windows.time.sleep"),
    ):
        assert computer._start_search_and_open("WhatsApp")
    assert [call.args[0] for call in input_driver.press.call_args_list] == [
        "win",
        "enter",
    ]
    input_driver.write.assert_called_once_with("WhatsApp", interval=0.03)
    wait.assert_called_once_with("WhatsApp", 8.0)


def test_file_workspace_blocks_secrets():
    root = Path(tempfile.mkdtemp())
    workspace = FileWorkspace()
    document = root / "notes.txt"
    assert "Wrote" in workspace.write_text(str(document), "hello")
    assert workspace.read_text(str(document)) == "hello"
    secret = root / ".env"
    secret.write_text("TOKEN=secret", encoding="utf-8")
    try:
        workspace.read_text(str(secret))
    except PermissionError:
        pass
    else:
        raise AssertionError("Credential files must remain blocked")


def test_presentation_generation():
    root = Path(tempfile.mkdtemp())
    output = PresentationBuilder(root).create(
        "JARVIS",
        "Overview\n- Voice assistant\n---\nCapabilities\n- Presentations",
        "System briefing",
    )
    path = Path(output)
    assert path.is_file()
    assert path.suffix == ".pptx"
    assert path.stat().st_size > 0


def test_destructive_terminal_commands_are_blocked():
    try:
        WindowsComputer().terminal("powershell -Command Remove-Item notes.txt")
    except PermissionError:
        pass
    else:
        raise AssertionError("Destructive terminal command must be blocked")


def test_voice_startup_configuration():
    from jarvis.voice.livekit_agent import (
        DEFAULT_GEMINI_MODEL,
        _configured_gemini_model,
        _manual_turn_control_enabled,
    )

    with patch.dict(
        os.environ,
        {
            "LIVEKIT_GEMINI_MODEL": "gemini-2.5-flash-native-audio-preview-12-2025",
        },
    ):
        assert _configured_gemini_model() == DEFAULT_GEMINI_MODEL
    assert not _manual_turn_control_enabled("dev", DEFAULT_GEMINI_MODEL)
    assert _manual_turn_control_enabled("dev", "compatible-legacy-model")


def test_voice_startup_state_messages():
    state = AssistantUiState()
    state.set_agent_state("initializing")
    state.set_status_message("Connecting Gemini voice")
    assert state.snapshot()["message"] == "Connecting Gemini voice"
    state.set_error("Voice startup timed out")
    snapshot = state.snapshot()
    assert snapshot["status"] == "error"
    assert snapshot["message"] == "Voice startup timed out"


if __name__ == "__main__":
    test_security()
    test_memory()
    test_ollama_latency_settings()
    test_ollama_warm_up()
    test_voice_capabilities_require_approval()
    test_voice_capabilities_honor_denial()
    test_voice_capabilities_trusted_mode_skips_approval()
    test_gemini_locator_parses_grounded_coordinates()
    test_visible_target_click_maps_screen_and_confirms_change()
    test_whatsapp_requires_approval()
    test_whatsapp_accepts_contact_names_and_phone_numbers()
    test_whatsapp_message_focuses_composer_and_verifies_send()
    test_whatsapp_detects_modern_composer_and_video_labels()
    test_whatsapp_control_lookup_scans_accessibility_tree_once()
    test_whatsapp_contact_search_uses_keyboard_fast_path()
    test_whatsapp_video_call_uses_accessible_button()
    test_whatsapp_call_uses_short_accessibility_fast_path()
    test_whatsapp_call_uses_visual_fallback_and_confirms_window()
    test_youtube_search_waits_for_loaded_page()
    test_system_status_reports_battery_and_usage()
    test_spotify_quick_search_selects_requested_song()
    test_spotify_playback_confirmation_uses_now_playing_bar()
    test_spotify_capability_uses_dedicated_media_action()
    test_windows_start_search_launch()
    test_file_workspace_blocks_secrets()
    test_presentation_generation()
    test_destructive_terminal_commands_are_blocked()
    test_voice_startup_configuration()
    test_voice_startup_state_messages()
    print("PASS")
