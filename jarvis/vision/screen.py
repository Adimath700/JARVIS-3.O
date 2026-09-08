from datetime import datetime
from pathlib import Path
import platform

try:
    import mss
    from PIL import Image, ImageChops, ImageStat
except ImportError:
    mss = None
    Image = None
    ImageChops = None
    ImageStat = None

try:
    import win32gui
except ImportError:
    win32gui = None


class ScreenVision:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

    def active_window(self):
        if win32gui is None:
            return "Unavailable outside Windows (pywin32 not installed)"
        window = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(window)
        return title or "Untitled window"

    def _capture_monitor(self, primary=False):
        if mss is None or Image is None:
            raise RuntimeError("mss/Pillow is not installed")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.output_dir / f"screen_{stamp}.png"
        with mss.mss() as sct:
            monitor = sct.monitors[1] if primary else sct.monitors[0]
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(path, "PNG")
        return path, monitor

    def capture(self, keep=True):
        path, _ = self._capture_monitor()
        return path

    def snapshot(self, primary=False):
        path, monitor = self._capture_monitor(primary)
        return {
            "platform": platform.platform(),
            "active_window": self.active_window(),
            "image": str(path),
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"],
        }

    @staticmethod
    def difference_ratio(before: str | Path, after: str | Path) -> float:
        if Image is None or ImageChops is None or ImageStat is None:
            raise RuntimeError("Pillow is not installed")
        with Image.open(before) as first, Image.open(after) as second:
            size = (160, 90)
            first_frame = first.convert("RGB").resize(size)
            second_frame = second.convert("RGB").resize(size)
            difference = ImageChops.difference(first_frame, second_frame)
            mean = ImageStat.Stat(difference).mean
        return sum(mean) / (len(mean) * 255)
