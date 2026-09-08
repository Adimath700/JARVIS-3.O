import compileall
import sys
from pathlib import Path

root = Path(__file__).parents[1]
python_ok = (
    compileall.compile_dir(root / "jarvis", quiet=1)
    and compileall.compile_file(root / "main.py", quiet=1)
    and compileall.compile_file(root / "agent.py", quiet=1)
)
ui_assets = [
    root / "jarvis/ui/web/index.html",
    root / "jarvis/ui/web/styles.css",
    root / "jarvis/ui/web/app.js",
]
ui_ok = all(path.is_file() and path.stat().st_size > 0 for path in ui_assets)

print("Python compile check:", "PASS" if python_ok else "FAIL")
print("Holographic UI assets:", "PASS" if ui_ok else "FAIL")
if not python_ok or not ui_ok:
    sys.exit(1)
