#!/usr/bin/env python3
"""bjbot — blackjack card counter & strategy advisor.

    python main.py calibrate   # one-time setup per casino site
    python main.py watch       # screen-watching mode with overlay
    python main.py manual      # type cards yourself, no vision needed
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
    args = parser.parse_args()

    if args.mode == "calibrate":
        from bjbot.calibrate import run_calibration
        run_calibration(CONFIG, TEMPLATES, args.monitor)
    elif args.mode == "watch":
        from bjbot.engine import run_watch
        run_watch(CONFIG, TEMPLATES)
    else:
        from bjbot.engine import run_manual
        run_manual(CONFIG if os.path.exists(CONFIG) else None)


if __name__ == "__main__":
    main()
