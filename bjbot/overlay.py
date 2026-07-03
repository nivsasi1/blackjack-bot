"""Always-on-top HUD overlay (tkinter, stdlib only).

The engine thread pushes state dicts via update_state(); the tkinter main
loop repaints at ~10 Hz. Green banner = favorable count, enter/raise bets.
"""

import threading
import tkinter as tk

REFRESH_MS = 100

GREEN = "#1d7a3c"
RED = "#7a1d1d"
DARK = "#1e1e28"
FG = "#f0ead6"


class Overlay:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict = {}
        self.root = tk.Tk()
        self.root.title("bjbot")
        self.root.attributes("-topmost", True)
        self.root.geometry("+20+20")
        self.root.configure(bg=DARK)
        self.root.resizable(False, False)

        self.banner = tk.Label(self.root, text="WAIT", font=("Arial", 22, "bold"),
                               bg=RED, fg=FG, width=22, pady=6)
        self.banner.pack(fill="x")
        self.counts = tk.Label(self.root, text="RC 0   TC 0.0   edge -0.50%",
                               font=("Consolas", 14), bg=DARK, fg=FG, pady=4)
        self.counts.pack(fill="x")
        self.advice = tk.Label(self.root, text="", font=("Arial", 18, "bold"),
                               bg=DARK, fg=FG, pady=4)
        self.advice.pack(fill="x")
        self.detail = tk.Label(self.root, text="hotkeys: F8 new shoe · F9 new round · F10 undo",
                               font=("Arial", 9), bg=DARK, fg="#9a94b8", pady=2)
        self.detail.pack(fill="x")
        self.root.after(REFRESH_MS, self._tick)

    def update_state(self, state: dict) -> None:
        with self._lock:
            self._state = dict(state)

    def _tick(self):
        with self._lock:
            s = self._state
        if s:
            if s.get("enter"):
                self.banner.config(
                    bg=GREEN,
                    text=f"ENTER — bet {s.get('bet_units', 1)}u  ({s.get('player_edge_pct', 0):+.2f}%)")
            else:
                self.banner.config(
                    bg=RED, text=f"WAIT  ({s.get('player_edge_pct', 0):+.2f}%)")
            self.counts.config(
                text=(f"RC {s.get('running_count', 0):+d}   "
                      f"TC {s.get('true_count', 0):+.1f}   "
                      f"decks left {s.get('decks_remaining', 0):.1f}"))
            move = s.get("move")
            if move:
                text = move["action"]
                if move.get("insurance"):
                    text += "  +INSURANCE"
                self.advice.config(text=text)
                self.detail.config(text=move.get("reason", ""))
            else:
                self.advice.config(text="")
                self.detail.config(
                    text="hotkeys: F8 new shoe · F9 new round · F10 undo")
        self.root.after(REFRESH_MS, self._tick)

    def run(self):
        self.root.mainloop()
