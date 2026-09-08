from pathlib import Path
import compileall, sys
root=Path(__file__).parents[1]
ok=compileall.compile_dir(root/'jarvis',quiet=1) and compileall.compile_file(root/'main.py',quiet=1)
print('Python compile check:', 'PASS' if ok else 'FAIL')
if not ok: sys.exit(1)
