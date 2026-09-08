import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from jarvis.brain.ollama import OllamaBrain
from jarvis.security.security import SecurityManager, Risk
from jarvis.memory.memory import Memory


def test_security():
    s = SecurityManager(Path(tempfile.mkdtemp()) / "a.log")
    assert s.classify("screen.capture") == Risk.LOW
    assert s.classify("terminal.exec") == Risk.HIGH


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


if __name__ == "__main__":
    test_security()
    test_memory()
    test_ollama_latency_settings()
    print("PASS")
