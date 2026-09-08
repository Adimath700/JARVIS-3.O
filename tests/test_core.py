import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from jarvis.brain.ollama import OllamaBrain
from jarvis.core.capabilities import JarvisCapabilities
from jarvis.memory.memory import Memory
from jarvis.security.security import Risk, SecurityManager


def test_security():
    log = Path(tempfile.mkdtemp()) / "a.log"
    s = SecurityManager(log)
    assert s.classify("screen.capture") == Risk.LOW
    assert s.classify("terminal.exec") == Risk.HIGH
    assert s.authorize(
        "keyboard.type",
        interactive=False,
        approved=True,
    ).allowed
    assert '"allowed": true' in log.read_text(encoding="utf-8")


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


if __name__ == "__main__":
    test_security()
    test_memory()
    test_ollama_latency_settings()
    test_voice_capabilities_require_approval()
    test_voice_capabilities_honor_denial()
    print("PASS")
