#!/usr/bin/env python3
"""bjbot — blackjack card counter & strategy advisor.

    python main.py calibrate   # one-time setup per casino site
    python main.py watch       # screen-watching mode with overlay
    python main.py manual      # type cards yourself, no vision needed
    python main.py sim         # Monte-Carlo EV / risk of a game + spread
"""

import argparse
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")
TEMPLATES = os.path.join(BASE, "templates")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    cal = sub.add_parser("calibrate", help="pick regions + capture rank templates")
    cal.add_argument("--monitor", type=int, default=1,
                     help="monitor index (mss numbering, default 1)")
    sub.add_parser("watch", help="watch the screen, count, advise")
    sub.add_parser("manual", help="manual card entry REPL")
    sm = sub.add_parser("sim", help="simulate a game's EV, risk of ruin, N0")
    sm.add_argument("--decks", type=int, default=8)
    sm.add_argument("--pen", type=float, default=0.5, help="penetration 0-1")
    sm.add_argument("--min-bet", type=float, default=5)
    sm.add_argument("--max-bet", type=float, default=100)
    sm.add_argument("--bet-per-tc", type=float, default=8)
    sm.add_argument("--enter-tc", type=float, default=2.0)
    sm.add_argument("--rounds", type=int, default=2_000_000)
    sm.add_argument("--rounds-per-hour", type=float, default=50)
    sm.add_argument("--bankroll", type=float, default=10_000)
    sm.add_argument("--h17", action="store_true", help="dealer hits soft 17")
    sm.add_argument("--no-das", action="store_true", help="no double after split")
    sm.add_argument("--surrender", action="store_true", help="late surrender allowed")
    sm.add_argument("--bj65", action="store_true", help="blackjack pays 6:5")
    sm.add_argument("--flat", action="store_true", help="flat bet (no ramp)")
    sm.add_argument("--play-all", action="store_true", help="don't wong out")
    args = parser.parse_args()

    if args.mode == "calibrate":
        from bjbot.calibrate import run_calibration
        run_calibration(CONFIG, TEMPLATES, args.monitor)
    elif args.mode == "watch":
        from bjbot.engine import run_watch
        run_watch(CONFIG, TEMPLATES)
    elif args.mode == "sim":
        from bjbot.simulator import SimConfig, SimRules, run_sim
        rules = SimRules(
            dealer_hits_soft_17=args.h17,
            double_after_split=not args.no_das,
            late_surrender=args.surrender,
            blackjack_pays=1.2 if args.bj65 else 1.5,
        )
        cfg = SimConfig(
            decks=args.decks, penetration=args.pen, min_bet=args.min_bet,
            max_bet=args.max_bet, bet_per_tc=args.bet_per_tc, enter_tc=args.enter_tc,
            rounds=args.rounds, rounds_per_hour=args.rounds_per_hour,
            bankroll=args.bankroll, flat=args.flat, wong=not args.play_all, rules=rules)
        r = run_sim(cfg)
        w = max(len(k) for k in r)
        for k, v in r.items():
            print(f"  {k.replace('_', ' '):<{w}}  {v}")
    else:
        from bjbot.engine import run_manual
        run_manual(CONFIG if os.path.exists(CONFIG) else None)


if __name__ == "__main__":
    main()
