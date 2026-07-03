"""Screen region capture via mss."""

import numpy as np

try:
    import cv2
    import mss
except ImportError:  # allow counter/strategy use without vision deps
    cv2 = None
    mss = None


class ScreenGrabber:
    """Grabs a fixed screen region as a grayscale numpy array."""

    def __init__(self, region: dict):
        # region: {"left": int, "top": int, "width": int, "height": int}
        if mss is None:
            raise RuntimeError("pip install mss opencv-python to use screen watch mode")
        self.region = region
        self._sct = mss.mss()

    def grab_gray(self) -> np.ndarray:
        frame = np.asarray(self._sct.grab(self.region))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def grab_bgr(self) -> np.ndarray:
        frame = np.asarray(self._sct.grab(self.region))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
