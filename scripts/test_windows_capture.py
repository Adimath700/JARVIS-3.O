from pathlib import Path
from jarvis.vision.screen import ScreenVision
v=ScreenVision(Path('data/screenshots'))
print('Active window:',v.active_window())
path=v.capture(); print('Screenshot:',path)
print('PASS')
