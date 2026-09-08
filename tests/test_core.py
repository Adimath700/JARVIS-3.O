import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
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
    test_whatsapp_requires_approval()
    test_whatsapp_accepts_contact_names_and_phone_numbers()
    test_windows_start_search_launch()
    test_file_workspace_blocks_secrets()
    test_presentation_generation()
    test_destructive_terminal_commands_are_blocked()
    test_voice_startup_configuration()
    test_voice_startup_state_messages()
    print("PASS")
