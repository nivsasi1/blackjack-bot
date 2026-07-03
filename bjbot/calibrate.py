"""Interactive calibration: pick screen regions and capture rank templates.

Run once per casino site / window layout:

    python main.py calibrate

Steps it walks you through:
1. Drag a box around the whole card area of the table (all dealt cards must
   land inside it) -> saved as `table` region.
2. Drag a box around where YOUR cards appear -> `player` region.
3. Drag a box around where the DEALER's upcard appears -> `dealer` region.
4. Template capture: with cards visible on screen, drag a tight box around a
   card's rank glyph (the letter/number in the corner), then type its rank.
   Repeat until all 13 ranks are captured; press ESC when done.
"""

import json
import os

import cv2
import mss
import numpy as np

from .counter import normalize_rank


def _fullscreen_shot(monitor_index: int = 1) -> tuple[np.ndarray, dict]:
    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        frame = np.asarray(sct.grab(mon))
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR), mon


def _select(win_title: str, image: np.ndarray) -> tuple[int, int, int, int]:
    print(f"\n>> {win_title}")
    print("   Drag a rectangle, then press ENTER/SPACE (or c to cancel).")
    r = cv2.selectROI(win_title, image, showCrosshair=True)
    cv2.destroyWindow(win_title)
    return tuple(int(v) for v in r)  # x, y, w, h


def _to_region(roi: tuple[int, int, int, int], mon: dict) -> dict:
    x, y, w, h = roi
    return {"left": mon["left"] + x, "top": mon["top"] + y,
            "width": w, "height": h}


def run_calibration(config_path: str, templates_dir: str,
                    monitor_index: int = 1) -> None:
    os.makedirs(templates_dir, exist_ok=True)
    shot, mon = _fullscreen_shot(monitor_index)

    config = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

    print("Make sure the blackjack table is visible on screen.")
    config["table"] = _to_region(
        _select("1/3 TABLE region (all dealt cards)", shot), mon)
    config["player"] = _to_region(
        _select("2/3 PLAYER cards region (your seat)", shot), mon)
    config["dealer"] = _to_region(
        _select("3/3 DEALER upcard region", shot), mon)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Regions saved to {config_path}")

    print("\nTemplate capture. Deal a few hands so different ranks show up.")
    print("For each visible card: drag a TIGHT box around the rank glyph in")
    print("its corner, press ENTER, then type the rank (A 2-9 10/T J Q K).")
    print("A fresh screenshot is taken each round. ESC / empty box to finish.")
    while True:
        shot, _ = _fullscreen_shot(monitor_index)
        roi = _select("Capture rank glyph (ESC when done)", shot)
        x, y, w, h = roi
        if w < 4 or h < 4:
            break
        crop = cv2.cvtColor(shot[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        raw = input("Rank of that card: ").strip()
        if not raw:
            continue
        try:
            rank = normalize_rank(raw)
        except ValueError as e:
            print(f"  {e} — skipped")
            continue
        n = len([f for f in os.listdir(templates_dir)
                 if f.startswith(rank)])
        name = f"{rank}.png" if n == 0 else f"{rank}_{n}.png"
        cv2.imwrite(os.path.join(templates_dir, name), crop)
        have = sorted({f.split("_")[0].split(".")[0]
                       for f in os.listdir(templates_dir) if f.endswith(".png")})
        print(f"  saved {name} | captured so far: {' '.join(have)}")

    print("Calibration done. Run: python main.py watch")
