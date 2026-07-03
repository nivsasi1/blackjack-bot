"""Watch mode (screen -> count -> advice -> overlay) and manual REPL mode."""

import json
import threading
import time

from .counter import CardCounter, normalize_rank
from .strategy import Rules, recommend

POLL_SECONDS = 0.25


def _load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_counter(cfg: dict) -> CardCounter:
    return CardCounter(
        decks=cfg.get("decks", 8),
        penetration=cfg.get("penetration", 0.5),
        base_house_edge=cfg.get("base_house_edge", 0.005),
        edge_per_tc=cfg.get("edge_per_tc", 0.005),
        enter_tc=cfg.get("enter_tc", 2.0),
    )


def _make_rules(cfg: dict) -> Rules:
    r = cfg.get("rules", {})
    return Rules(
        dealer_hits_soft_17=r.get("dealer_hits_soft_17", True),
        double_after_split=r.get("double_after_split", True),
        late_surrender=r.get("late_surrender", True),
        insurance_tc=r.get("insurance_tc", 3.0),
    )


# --------------------------------------------------------------------------
# Watch mode
# --------------------------------------------------------------------------

def run_watch(config_path: str, templates_dir: str) -> None:
    import cv2  # noqa: F401 — fail fast with a clear message if missing
    from pynput import keyboard

    from .capture import ScreenGrabber
    from .detector import CardDetector, load_templates
    from .overlay import Overlay

    cfg = _load_config(config_path)
    for key in ("table", "player", "dealer"):
        if key not in cfg:
            raise SystemExit(f"config has no '{key}' region — run: python main.py calibrate")
    templates = load_templates(templates_dir)
    if not templates:
        raise SystemExit(f"no templates in {templates_dir} — run: python main.py calibrate")
    missing = [r for r in "A23456789TJQK" if r not in templates]
    if missing:
        print(f"WARNING: no template for rank(s): {' '.join(missing)} — "
              "those cards will NOT be counted. Re-run calibrate to add them.")

    counter = _make_counter(cfg)
    rules = _make_rules(cfg)
    table_det = CardDetector(templates)
    hand_det = CardDetector(templates)  # stateless per-frame matcher for hands
    table_grab = ScreenGrabber(cfg["table"])
    player_grab = ScreenGrabber(cfg["player"])
    dealer_grab = ScreenGrabber(cfg["dealer"])
    overlay = Overlay()

    def on_new_shoe():
        counter.new_shoe()
        table_det.reset_round()
        print("[hotkey] new shoe — count reset")

    def on_new_round():
        table_det.reset_round()
        print("[hotkey] new round — table positions cleared")

    def on_undo():
        rank = counter.undo()
        print(f"[hotkey] undo {rank or '(nothing)'}")

    hotkeys = keyboard.GlobalHotKeys({
        "<f8>": on_new_shoe, "<f9>": on_new_round, "<f10>": on_undo})
    hotkeys.daemon = True
    hotkeys.start()

    def loop():
        while True:
            try:
                for rank, _pos in table_det.feed(table_grab.grab_gray()):
                    counter.see(rank)
                    print(f"seen {rank}  RC {counter.running_count:+d}  "
                          f"TC {counter.true_count:+.1f}")

                player_hits = hand_det._match_frame(player_grab.grab_gray())
                dealer_hits = hand_det._match_frame(dealer_grab.grab_gray())
                state = counter.status()
                if len(player_hits) >= 2 and dealer_hits:
                    player_cards = [h[0] for h in sorted(player_hits, key=lambda h: h[1][0])]
                    dealer_up = max(dealer_hits, key=lambda h: h[2])[0]
                    state["move"] = recommend(
                        player_cards, dealer_up, counter.true_count, rules)
                overlay.update_state(state)
            except Exception as e:  # keep the loop alive on transient errors
                print(f"[watch] {e}")
            time.sleep(POLL_SECONDS)

    threading.Thread(target=loop, daemon=True).start()
    print("Watching. Overlay is up. F8 new shoe · F9 new round · F10 undo.")
    overlay.run()


# --------------------------------------------------------------------------
# Manual mode
# --------------------------------------------------------------------------

HELP = """\
Commands:
  5 k a 10 ...        count cards as they are dealt (any ranks, spaces between)
  h <cards> v <up>    advice for your hand, e.g.:  h a 7 v 9   /  h 8 8 v 10
                      (cards given here are NOT re-counted)
  u                   undo last counted card
  n                   new shoe (reset count)
  s                   status
  q                   quit
"""


def _print_status(counter: CardCounter) -> None:
    s = counter.status()
    flag = "ENTER ✅" if s["enter"] else "wait"
    print(f"  RC {s['running_count']:+d} | TC {s['true_count']:+.1f} | "
          f"decks left {s['decks_remaining']} | edge {s['player_edge_pct']:+.2f}% | "
          f"{flag} | bet {s['bet_units']}u")


def run_manual(config_path: str | None = None) -> None:
    cfg = {}
    if config_path:
        try:
            cfg = _load_config(config_path)
        except FileNotFoundError:
            pass
    counter = _make_counter(cfg)
    rules = _make_rules(cfg)
    print(f"Manual mode — {counter.decks} decks, Hi-Lo. Type '?' for help.\n")
    _print_status(counter)

    while True:
        try:
            line = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("q", "quit", "exit"):
            break
        if line in ("?", "help"):
            print(HELP)
            continue
        if line == "u":
            rank = counter.undo()
            print(f"  undid {rank}" if rank else "  nothing to undo")
            _print_status(counter)
            continue
        if line == "n":
            counter.new_shoe()
            print("  new shoe")
            _print_status(counter)
            continue
        if line == "s":
            _print_status(counter)
            continue
        if line.startswith("h ") and " v " in line:
            try:
                hand_part, up = line[2:].rsplit(" v ", 1)
                move = recommend(hand_part.split(), up.strip(),
                                 counter.true_count, rules)
                extra = "  + take INSURANCE" if move["insurance"] else ""
                print(f"  ▶ {move['action']}{extra}   "
                      f"({move['reason']}; total {move['total']}"
                      f"{' soft' if move['soft'] else ''})")
            except ValueError as e:
                print(f"  {e}")
            continue
        # otherwise: a list of dealt cards to count
        try:
            ranks = [normalize_rank(t) for t in line.split()]
        except ValueError as e:
            print(f"  {e} (type '?' for help)")
            continue
        for r in ranks:
            counter.see(r)
        _print_status(counter)

    print("bye")
