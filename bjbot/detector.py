"""Card-rank detection by template matching.

Templates are grayscale crops of each rank's corner glyph, captured during
calibration for the specific casino UI (templates/A.png ... templates/K.png,
extra variants as A_2.png etc.). Detection runs matchTemplate over the table
region each frame; a hit must stay put for STABLE_FRAMES consecutive frames
before it is counted, and a counted position is remembered so the same card
on the felt is never counted twice.
"""

import os
from dataclasses import dataclass, field

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from .counter import RANKS

MATCH_THRESHOLD = 0.84   # matchTemplate score required to accept a hit
STABLE_FRAMES = 3        # consecutive frames a hit must persist
POSITION_TOLERANCE = 14  # px — same-card radius across frames
SCALES = (0.85, 1.0, 1.15)  # tolerate small zoom differences vs calibration


def load_templates(directory: str) -> dict[str, list[np.ndarray]]:
    templates: dict[str, list[np.ndarray]] = {}
    for name in sorted(os.listdir(directory)):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        rank = stem.split("_")[0].upper()
        if rank == "10":
            rank = "T"
        if rank not in RANKS:
            continue
        img = cv2.imread(os.path.join(directory, name), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            templates.setdefault(rank, []).append(img)
    return templates


@dataclass
class _Candidate:
    rank: str
    pos: tuple[int, int]
    frames: int = 1


@dataclass
class CardDetector:
    templates: dict[str, list[np.ndarray]]
    threshold: float = MATCH_THRESHOLD
    counted: list = field(default_factory=list)      # positions already counted
    candidates: list = field(default_factory=list)   # hits awaiting stability

    def reset_round(self) -> None:
        """Call when the felt is cleared — positions can be reused next round."""
        self.counted.clear()
        self.candidates.clear()

    def _near(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        return (abs(a[0] - b[0]) <= POSITION_TOLERANCE
                and abs(a[1] - b[1]) <= POSITION_TOLERANCE)

    def _match_frame(self, gray: np.ndarray) -> list[tuple[str, tuple[int, int], float]]:
        hits = []
        for rank, tpls in self.templates.items():
            for tpl in tpls:
                for scale in SCALES:
                    t = tpl if scale == 1.0 else cv2.resize(
                        tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                    th, tw = t.shape
                    if th >= gray.shape[0] or tw >= gray.shape[1]:
                        continue
                    res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
                    ys, xs = np.where(res >= self.threshold)
                    for x, y in zip(xs, ys):
                        hits.append((rank, (int(x), int(y)), float(res[y, x])))
        # non-max suppression: keep the best-scoring hit per location
        hits.sort(key=lambda h: -h[2])
        kept: list[tuple[str, tuple[int, int], float]] = []
        for h in hits:
            if not any(self._near(h[1], k[1]) for k in kept):
                kept.append(h)
        return kept

    def feed(self, gray: np.ndarray) -> list[tuple[str, tuple[int, int]]]:
        """Process one frame; return newly confirmed cards as (rank, pos)."""
        hits = self._match_frame(gray)
        new_cards: list[tuple[str, tuple[int, int]]] = []
        seen_this_frame = []

        for rank, pos, _score in hits:
            if any(self._near(pos, c) for c in self.counted):
                continue  # already counted this physical card
            cand = next((c for c in self.candidates
                         if c.rank == rank and self._near(pos, c.pos)), None)
            if cand is None:
                cand = _Candidate(rank, pos)
                self.candidates.append(cand)
            else:
                cand.frames += 1
                cand.pos = pos
            seen_this_frame.append(cand)
            if cand.frames >= STABLE_FRAMES:
                self.counted.append(pos)
                self.candidates.remove(cand)
                new_cards.append((rank, pos))

        # candidates that vanished were noise — drop them
        self.candidates = [c for c in self.candidates if c in seen_this_frame]
        return new_cards
