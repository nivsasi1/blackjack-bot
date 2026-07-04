# bjbot — blackjack card counter & strategy advisor

Watches a blackjack table on **your own screen**, keeps a running count,
flags when the shoe turns favorable (with an estimated player-edge % and
Kelly bet size), and recommends the mathematically best move — hit / stand
/ double / split / surrender / insurance — including the Illustrious 18 +
Fab 4 count-based deviations from basic strategy.

Eight counting systems are built in: **Hi-Lo** (default), **KO** and
**Red 7** (unbalanced — no true-count division; IRC/key-count/pivot),
**Hi-Opt I/II** and **Omega II** (ace-neutral, with automatic ace
side-count adjustment of the betting count), **Zen**, and **Wong Halves**.
The math behind every constant — system tables, true-count conventions,
edge model, index values, Kelly/risk formulas, live-dealer viability — is
researched and sourced in [docs/COUNTING.md](docs/COUNTING.md).

Runs entirely locally. Nothing is automated — it never clicks or bets for
you; it only reads pixels and shows advice in an always-on-top overlay.

## Read this first (honestly)

- **Counting only works on live-dealer shoe games.** RNG/virtual blackjack
  shuffles every round, so the count is permanently ~0 and this tool is
  useless there. Live tables that cut off half of an 8-deck shoe (typical)
  give only a thin edge even played perfectly.
- **Casino terms of service prohibit assistance software.** Real-money
  accounts get banned and winnings confiscated when it's detected. In
  physical casinos, using a *device* to aid play is a crime in some
  jurisdictions (e.g. Nevada NRS 465.075).
- Treat this as a **practice / analysis / study tool**. The manual mode is a
  great counting trainer.

## Install

```bash
cd blackjack-bot
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

Python 3.10+. `tkinter` ships with most Python installs (on Debian/Ubuntu:
`sudo apt install python3-tk`). On macOS, grant the terminal **Screen
Recording** and **Accessibility** permissions (System Settings → Privacy).

## 1. Calibrate (once per casino site / window layout)

Open the blackjack table on screen, then:

```bash
python main.py calibrate
```

It walks you through dragging four things on a screenshot:

1. **Table region** — a box covering everywhere dealt cards land. Every card
   inside it gets counted.
2. **Player region** — where *your* two cards appear (used for move advice).
3. **Dealer region** — where the dealer's upcard appears.
4. **Rank templates** — for each visible card, drag a *tight* box around the
   rank glyph in its corner (the "K", "7", "10"…), press Enter, type the
   rank. Deal a few hands until you've captured all 13 ranks (A 2–9 10 J Q
   K). A fresh screenshot is taken before each capture. More than one
   template per rank is fine and improves robustness.

Regions go to `config.json`, glyph images to `templates/`. Keep the game
window at the same position/zoom afterwards — if you move it, recalibrate.

## 2. Watch

```bash
python main.py watch
```

A small always-on-top HUD appears:

- **Banner** — red `WAIT` while the count is bad/neutral; green
  **`ENTER — bet Nu (+0.75%)`** when the true count reaches your `enter_tc`
  threshold (default +2). The percentage is your estimated edge for the next
  round; the bet is a simple (TC−1)-unit ramp.
- **Counts row** — running count, true count, decks remaining.
- **Move line** — when your cards + the dealer upcard are detected, the best
  action (`HIT` / `STAND` / `DOUBLE` / `SPLIT` / `SURRENDER`, plus
  `+INSURANCE` when TC ≥ +3 against an ace) and whether it comes from basic
  strategy or a count deviation.

Global hotkeys: **F8** new shoe (reset count at the shuffle), **F9** new
round (tells the tracker the felt was cleared, so card positions can be
reused), **F10** undo the last counted card (misdetection fix).

Detection notes: a card is counted after its rank glyph is seen at the same
spot for 3 consecutive frames, and each spot is counted once per round — so
press **F9 between rounds**; that's what prevents double counting. Watch the
terminal: every counted card is logged (`seen K  RC -1  TC -0.1`), so you
can verify accuracy against the table and F10 any mistakes.

## Manual mode (no calibration needed — also a great trainer)

```bash
python main.py manual
```

```
> 5 k a 10          # count cards as they're dealt
  RC -2 | TC -0.3 | decks left 7.9 | edge -0.63% | wait | bet 1u
> h a 7 v 9         # "what do I do with A,7 vs dealer 9?"
  ▶ HIT   (basic strategy; total 18 soft)
> h 10 6 v 10
  ▶ SURRENDER   (basic strategy; total 16)
```

`u` undo · `n` new shoe · `s` status · `q` quit.

## Configuration (`config.json`)

Copy `config.example.json` if you want to hand-edit. Key settings:

| key | default | meaning |
|---|---|---|
| `system` | "hi-lo" | counting system: `hi-lo`, `ko`, `red-7`, `hi-opt-1`, `hi-opt-2`, `omega-2`, `zen`, `wong-halves` |
| `decks` | 8 | decks in the shoe (live tables are usually 8, some 6) |
| `enter_tc` | 2.0 | true count that triggers the green ENTER flag (unbalanced systems use their key count instead) |
| `edge_per_tc` | 0.005 | edge gained per true-count point (~0.5% standard) |
| `base_house_edge` | *(auto)* | omit to estimate it from `rules`; set explicitly to override |
| `tc_method` | "exact" | TC display convention: `exact` / `floor` / `round` / `trunc` |
| `half_deck_divisor` | true | divide by decks remaining to the nearest half deck |
| `bankroll` | 0 | set > 0 to get Kelly bet sizing in the status |
| `kelly_divisor` | 2.0 | 2 = half-Kelly (recommended), 1 = full Kelly |
| `rules.dealer_hits_soft_17` | true | H17 vs S17 |
| `rules.double_after_split` | true | DAS |
| `rules.late_surrender` | true | set false if the table has no surrender |
| `rules.blackjack_pays_65` | false | 6:5 blackjack (adds +1.39% house edge — don't play these) |
| `rules.insurance_tc` | 3.0 | take insurance at/above this true count |

Edge estimate = `betting TC × edge_per_tc − base_house_edge` — the
standard approximation (TC +1 ≈ break-even, +2 ≈ +0.5%, +3 ≈ +1%). When
`base_house_edge` is omitted it is derived from your rule set using
Wizard-of-Odds anchor figures (see docs/COUNTING.md §4).

## Tests

```bash
python test_bjbot.py   # 91 checks over the counter + strategy engines
```

## Layout

```
main.py              CLI entry (calibrate / watch / manual)
docs/COUNTING.md     the research: systems, TC math, edge model, indices, Kelly
bjbot/counter.py     8 counting systems, true/betting count, edge %, Kelly
bjbot/strategy.py    basic strategy tables + Illustrious 18 + Fab 4 indices
bjbot/capture.py     mss screen-region grabber
bjbot/detector.py    template matching, stability filter, dedup per round
bjbot/calibrate.py   region picker + rank-glyph template capture
bjbot/overlay.py     tkinter always-on-top HUD
bjbot/engine.py      watch loop and manual REPL
```
