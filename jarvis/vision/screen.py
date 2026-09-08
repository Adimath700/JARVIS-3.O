from pathlib import Path
from datetime import datetime
import os, platform
try:
    import mss
    from PIL import Image
except ImportError: mss=Image=None
try:
    import win32gui
except ImportError: win32gui=None

class ScreenVision:
    def __init__(self, output_dir:Path): self.output_dir=output_dir; output_dir.mkdir(parents=True,exist_ok=True)
    def active_window(self):
        if win32gui is None: return 'Unavailable outside Windows (pywin32 not installed)'
        hwnd=win32gui.GetForegroundWindow(); title=win32gui.GetWindowText(hwnd)
        return title or 'Untitled window'
    def capture(self,keep=True):
        if mss is None: raise RuntimeError('mss/Pillow is not installed')
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f'); path=self.output_dir/f'screen_{stamp}.png'
        with mss.mss() as sct:
            monitor=sct.monitors[0]
            shot=sct.grab(monitor)
            img=Image.frombytes('RGB',shot.size,shot.rgb)
            img.save(path,'PNG')
        if not keep: return path
        return path
    def snapshot(self): return {'platform':platform.platform(),'active_window':self.active_window(),'image':str(self.capture())}
