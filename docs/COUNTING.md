# Card counting — the research behind bjbot's numbers

This document is the deep-dive reference for every constant in
`bjbot/counter.py` and `bjbot/strategy.py`. Figures were cross-checked
against multiple published sources (July 2026); the primary literature is
Griffin's *The Theory of Blackjack*, Schlesinger's *Blackjack Attack*,
Wong's *Professional Blackjack*, Vancura & Fuchs' *Knock-Out Blackjack*,
Snyder's *Blackbelt in Blackjack*, and the Wizard of Odds / QFIT (Norm
Wattenberger) simulation sites.

## 1. Why counting works

Blackjack rounds are not independent: cards leave the shoe. High cards
(T, A) favor the **player** — more blackjacks (paid 3:2 while the dealer's
blackjack only takes your 1 unit), better double-downs, and the dealer
busts stiffs more often because the dealer *must* hit. Low cards (2–6)
favor the **dealer** — they land on dealer stiffs (12–16) and convert them
into made hands. A count is a running estimate of the high/low imbalance
of the cards still in the shoe. Thorp proved the game beatable this way in
*Beat the Dealer* (1962); every modern system is a refinement of the same
"effects of removal" analysis (Griffin).

Two ways the counter cashes the information in:

1. **Bet variation** — bet small (or nothing) when the shoe favors the
   house, big when it favors you. In 6–8 deck shoe games this is the large
   majority of the total gain, which is why Betting Correlation is the
   metric that matters for shoe play.
2. **Play variation** — deviate from basic strategy when the count says
   so (the index plays, §5). Worth much less in shoes; the insurance index
   alone is over 30% of all play-variation gain, and the "Big 3"
   (insurance, 16v10, 15v10) are nearly 60% (Schlesinger).

## 2. Counting systems

Tag values per rank (sum over a full deck = 0 for balanced systems):

| System | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | T/J/Q/K | A | Level | Balanced | BC | PE | IC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Hi-Lo** | +1 | +1 | +1 | +1 | +1 | 0 | 0 | 0 | −1 | −1 | 1 | yes | .97 | .51 | .76 |
| **KO** | +1 | +1 | +1 | +1 | +1 | **+1** | 0 | 0 | −1 | −1 | 1 | no | .98 | .55 | .78 |
| **Red 7** | +1 | +1 | +1 | +1 | +1 | +1 red / 0 black | 0 | 0 | −1 | −1 | 1 | no | .98 | .54 | .78 |
| **Hi-Opt I** | 0 | +1 | +1 | +1 | +1 | 0 | 0 | 0 | −1 | **0** | 1 | yes | .88 | .61 | .85 |
| **Hi-Opt II** | +1 | +1 | +2 | +2 | +1 | +1 | 0 | 0 | −2 | **0** | 2 | yes | .91 | .67 | .91 |
| **Omega II** | +1 | +1 | +2 | +2 | +2 | +1 | 0 | −1 | −2 | **0** | 2 | yes | .92 | .67 | .85 |
| **Zen** | +1 | +1 | +2 | +2 | +2 | +1 | 0 | 0 | −2 | −1 | 2 | yes | .96 | .63 | .85 |
| **Wong Halves** | +½ | +1 | +1 | +1½ | +1 | +½ | 0 | −½ | −1 | −1 | 3 | yes | .99 | .56 | .72 |

*BC/PE/IC values are the Griffin-derived figures reproduced in the
Blackjack Review encyclopedia's system-comparison table; small variations
(±.01–.02) exist between editions.*

What the metrics mean (Griffin):

- **BC — Betting Correlation**: correlation between the count's tags and
  each card's actual effect on the *bet* (next-round) EV. Determines how
  well the count finds the profitable rounds. **This is what matters in
  6–8 deck shoes** — the deviation plays are rare there, the betting
  decision happens every round.
- **PE — Playing Efficiency**: how well the count drives strategy
  departures. Caps out around 0.70 for any single-parameter count. Matters
  in single/double deck, where you're dealt into rich/poor subsets fast.
- **IC — Insurance Correlation**: how well the count prices insurance
  (a pure ten-density bet — the "perfect insurance count" tags
  2–9 = +1, T = −2, A = 0). Level-2 counts with T = −2 do this better.

Practical takeaways (echoed by Schlesinger's "what's the best system"
analysis in *Blackjack Attack*): for shoe games, **Hi-Lo, KO and Zen are
within a few percent of each other in dollar terms**; the fancy level-2/3
systems buy almost nothing in a shoe and cost error rate. The pros' actual
consensus is Hi-Lo, because every published index table and simulation
assumes it. That's why it's bjbot's default.

**Ace-neutral systems** (Hi-Opt I/II, Omega II) don't count the ace, which
is right for *playing* decisions (the ace acts like a low card once you're
drawing) but wrong for *betting* (aces make blackjacks). They need an
**ace side count**: compare aces seen to the pro-rata share; each excess
ace remaining is worth about +1 Hi-Lo-equivalent point (+2 in level-2
tags) added to the betting count only. Side-counting aces lifts Omega II's
effective BC from .92 to ≈.99. `CardCounter.betting_count` implements
exactly this adjustment.

## 3. Running count → decision number

### Balanced systems: true count

`TC = RC / decks remaining`. Conventions that differ between books
(verified against Wattenberger's "True Count Calculation — The Whole
Story" and the CVData docs):

- **Divisor resolution**: full decks, half decks (most common; what bjbot
  uses — `half_deck_divisor`), or quarter decks. Finer isn't automatically
  better; indices must be generated with the same convention.
- **Result handling**: **floor** (next lower integer, what most published
  indices including Schlesinger's assume), **truncate** (toward zero —
  Wong's *Professional Blackjack* 1994+), or **round**. Example: RC −2
  with 4 decks left = −0.5 → floor −1, truncate 0.
- For **integer thresholds the distinction doesn't change decisions**
  (floor(tc) ≥ idx ⟺ tc ≥ idx), which is why bjbot keeps the exact float
  internally and only applies `tc_method` for display/training.

### Unbalanced systems: IRC, key count, pivot

KO counts the 7 as +1, so a full deck sums to **+4** (Red 7: red sevens
only, +2/deck). The count is seeded with a negative **IRC** so that the
interesting region lands at fixed running-count landmarks and *no division
is ever needed*:

| | KO | Red 7 |
|---|---|---|
| IRC | `4 − 4×decks` (1D: 0, 2D: −4, 6D: −20, 8D: −28) | `−2×decks` (6D: −12, 8D: −16) |
| **Key count** (start betting up) | 1D +2, 2D +1, 4D −1, 6D −4, 8D −6 | ≈ pivot (0) for shoes |
| **Pivot** (max bet; exact TC-equivalent) | always **+4** ≡ Hi-Lo TC +4 | always **0** ≡ TC +2 |

The pivot is exact at any shoe depth: at pivot RC the remaining cards have
exactly the pivot's Hi-Lo-equivalent true count. Between landmarks the
equivalence drifts with depth; bjbot interpolates
`TC_equiv = (RC − pivot_rc)/decks_remaining + pivot_tc` to keep using the
Hi-Lo index tables and edge model with unbalanced counts. (KO's own book
instead publishes fixed RC-based strategy numbers; the interpolation is
the standard reconciliation and is exact at the pivot.)

## 4. Edge model

- **Off the top** the player is behind by the base house edge. Verified
  anchor points (Wizard of Odds calculator figures): 6 decks, H17, DAS,
  no LS, 3:2 ≈ **0.64%**; S17 is worth **−0.22%**; LS ≈ −0.08%; no-DAS
  ≈ +0.14%; 8 decks ≈ +0.02% vs 6; **6:5 blackjack +1.39%** (an 8D S17
  DAS game goes 0.41% → ≈1.77% — unbeatable, never play 6:5).
  `estimate_base_house_edge()` reproduces these.
- **Each +1 true count ≈ +0.5% player EV** for standard shoe rules — the
  standard Hi-Lo figure from Schlesinger's simulations; the actual range
  across rule sets is ~0.45–0.55%/TC. So TC +1 ≈ break-even, TC +2 ≈
  +0.5%, TC +4 ≈ +1.5% with a 0.5% base game.
- bjbot: `player_edge = betting_TC × edge_per_tc − base_house_edge`.

### Penetration — the number that decides everything

The count only spreads away from zero as cards are dealt; the rich/poor
extremes live in the **back of the shoe**. Cut off 4 of 8 decks and the
high-count rounds barely ever materialize. Expert consensus (Wizard of
Vegas / bj21 threads, Wattenberger's charts): an 8-deck game with 50%
penetration is *technically* beatable but marginal to the point of
pointlessness played all-hands; **back-counting (wonging) is the only
sensible way to play it**. 75%+ penetration is what counters actually
look for; each extra half-deck dealt is worth more than most rule
improvements.

## 5. Index plays

### The Illustrious 18 (Schlesinger, *Blackjack Attack* — Hi-Lo, multi-deck)

The 18 deviations worth ~80–90% of all play-variation gain, in roughly
descending value. bjbot implements all of them (`strategy.DEVIATIONS`):

| # | Play | Index (TC) | # | Play | Index (TC) |
|---|---|---|---|---|---|
| 1 | **Insurance** | **+3** | 10 | 10 v A double | +4 |
| 2 | 16 v 10 stand | 0 | 11 | 9 v 2 double | +1 |
| 3 | 15 v 10 stand | +4 | 12 | 10,10 v 5 split | +5 |
| 4 | 12 v 3 stand | +2 | 13 | 10,10 v 6 split | +4 |
| 5 | 12 v 2 stand | +3 | 14 | 12 v 4 stand | 0 |
| 6 | 11 v A double | +1 | 15 | 12 v 5 stand | −2 |
| 7 | 9 v 7 double | +3 | 16 | 12 v 6 stand | −1 |
| 8 | 16 v 9 stand | +5 | 17 | 13 v 3 stand | −2 |
| 9 | 13 v 2 stand | −1 | 18 | 10 v 10 double | +4 |

Notes: negative indices are "keep standing until the count drops below" —
they earn their keep when you must play through negative shoes; a pure
back-counter can skip them. Exact values shift ±1 with decks/rules and
index-generation method (EV-max vs risk-averse, floored vs rounded); the
table above is the classic BJA3 multi-deck set. Under H17, 11 v A is
already basic strategy (no index needed) — bjbot's rules engine handles
that automatically.

### The Fab Four (surrender indices, when late surrender exists)

| Play | Index |
|---|---|
| 15 v 10 surrender | 0 (take it back below 0) |
| 15 v A surrender | +1 (H17 ≈ −1; rule-sensitive) |
| 15 v 9 surrender | +2 |
| 14 v 10 surrender | +3 |

Schlesinger: with LS available, the Fab 4 are worth more than I18 entries
10–18 combined. bjbot implements the table above and gives the surrender
plays precedence over the stand/hit indices for 15/16 vs 9/10/A on
two-card hands.

### Risk-averse indices

EV-maximizing indices ignore variance; risk-averse (RA) indices shade a
few doubles/splits (e.g. 10 v 10, 9 v 7) a point higher because doubling
puts more money out at nearly-flat EV. The difference is small; bjbot uses
the classic EV-max table.

## 6. Bet sizing

- **Kelly**: the growth-optimal stake for a hand with edge `e` and
  variance `v` is `bankroll × e / v`, with blackjack per-hand variance
  ≈ **1.32** (SD ≈ 1.15 bets). At TC +3 (edge ≈ +1%) with a 10,000
  bankroll that's ≈ 75 units of 1 — Kelly bets are *bigger* than intuition
  suggests, which is why **half-Kelly** (`kelly_divisor: 2`) is the
  near-universal practice: ~75% of the growth at half the volatility, and
  it buffers the fact that your edge estimate itself is noisy.
  `CardCounter.kelly_bet()` implements `bankroll × edge / 1.32 / divisor`.
- **Practical ramps**: real counters use a stepped ramp approximating
  Kelly, e.g. 1 unit at TC ≤ +1, then roughly (TC−1) units, capping at a
  spread the game tolerates. Shoe games need a **big spread to beat the
  house baseline: 1–8 minimum, 1–12/1–15 typical** for 6–8 deck; a 1–2
  spread cannot beat a shoe. `bet_units()` is the (TC−1) ramp.
- **Wonging / back-counting**: watch without betting, sit down at TC ≥ +2
  (bjbot's `enter_tc` default, the classic wong-in point at which you're
  ~+0.5%), leave when it drops (wong-out around 0/−1). Back-counting
  never plays negative EV hands, so it turns even poor-penetration shoes
  weakly positive — at the cost of playing far fewer hands/hour.
- **Risk of ruin**: with edge `e`, variance `v`, bankroll `B` (in units),
  the classic approximation is `RoR = exp(−2eB/v)`. Schlesinger's
  benchmarks: **SCORE** (Standardized COmparison Of Risk and Expectation)
  = win rate per 100 hands with a $10k bankroll at 13.5% RoR — effectively
  `edge²/variance` scaled — for comparing games apples-to-apples; **N0**
  ("N-zero") = hands needed for expectation to overcome one standard
  deviation (≈ `v/e²`), i.e. how long until you're reliably ahead. For a
  marginal game N0 easily exceeds 100k hands — worth computing before
  caring about a game.

## 7. Live-dealer online reality check (why the WAIT banner is mostly red)

Verified practitioner numbers:

- Live-dealer blackjack is typically **8 decks, ~50% penetration** (the
  shuffle point is around 4 decks), 3:2, H17 or S17 by studio. Cards are
  visible to OCR/vision — which is what makes bjbot possible — but the cut
  card kills most of the value: high-TC rounds are rare when half the shoe
  never gets dealt.
- Blackjack Apprenticeship's simulation of the *best* live-dealer
  conditions: **≈ $1/hour EV at 50 rounds/hour** (less on slow tables),
  needing a **~$40,000 bankroll for <1% risk of ruin** — versus ≈ $19/hour
  on the same rules in a physical casino with normal penetration and
  speed, on a $17,000 bankroll.
- Jim Makos' live-play analysis reaches the same verdict: counting live
  online blackjack "nearly works" — real but unpayable edge once game
  speed (~20–50 hands/hour) and penetration are priced in.
- **RNG blackjack** (and physical **CSM** tables) shuffle every round:
  the count never leaves ~0; nothing to count, ever.
- And the standing caveat: casino ToS ban assistance software; detection
  means confiscation. Treat all of this as study/practice tooling.

## 8. What bjbot implements, mapped

| Concept | Code |
|---|---|
| 8 systems, tags + BC/PE/IC | `counter.SYSTEMS` |
| IRC / key count / pivot (KO, Red 7) | `CountSystem.irc/pivot_rc`, `CardCounter.key_count` |
| TC conversion (half-deck divisor, floor/round/trunc display) | `CardCounter.true_count/displayed_tc` |
| Ace side count for ace-neutral systems | `CardCounter.excess_aces/betting_count` |
| Edge model (−base + 0.5%/TC) | `CardCounter.player_edge`, `estimate_base_house_edge` |
| Illustrious 18 + Fab 4 | `strategy.DEVIATIONS` |
| Wong-in flag | `CardCounter.should_enter` (TC threshold / key count) |
| Kelly + ramp | `CardCounter.kelly_bet/bet_units` |

## Sources

- [Blackjack Review encyclopedia — system comparisons](https://www.blackjackreview.com/wp/encyclopedia/card-counting-system-comparisons/) (Griffin's BC/PE/IC tables)
- [Blackjack Review — I is for Illustrious 18](https://www.blackjackreview.com/wp/encyclopedia/i/) · [F is for Fab 4](https://www.blackjackreview.com/wp/encyclopedia/f/)
- [CountingEdge — Illustrious 18 indices](https://www.countingedge.com/blackjack-players/don-schlesinger/the-illustrious-18-card-counting-indices/) · [SCORE](https://www.countingedge.com/blackjack-players/don-schlesinger/the-score-index-in-blackjack/)
- [QFIT (Wattenberger) — True Count Calculation, the whole story](https://www.qfit.com/CalculatingTrueCounts.htm) · [CV True Count Calculator docs](https://www.qfit.com/cvblackjackhelp/truecountcalculator.htm) · [Red Seven](https://www.qfit.com/cardcounting/Red-Seven/) · [REKO](https://www.qfit.com/rekostrategy.htm)
- [Wizard of Odds — Hi-Lo intro](https://wizardofodds.com/games/blackjack/card-counting/high-low/) · [house edge calculator](https://wizardofodds.com/games/blackjack/calculator/) · [rule variations](https://wizardofodds.com/ask-the-wizard/blackjack/house-edge/) · [Kelly criterion](https://wizardofodds.com/gambling/kelly-criterion/)
- [Blackjack Apprenticeship — card counting online](https://www.blackjackapprenticeship.com/card-counting-online/) · [system comparison](https://www.blackjackapprenticeship.com/card-counting-systems/)
- [Jim Makos — Card counting nearly works in live blackjack online](https://jimmakos.com/live-blackjack-online-card-counting/)
- [Wizard of Vegas forum — 8-deck, 50% penetration threads](https://wizardofvegas.com/forum/gambling/blackjack/21275-8-deck-game-50-penetration/) · [bj21 — importance of penetration](https://bj21.com/articles/card-counting/importance-of-penetration)
- KO parameters: [BonusInsider — the KO system](https://www.bonusinsider.com/blackjack/the-knock-out-card-counting-system/) and blackjackinfo forum threads on IRC/key/pivot
- Thorp, [*The Kelly Criterion in Blackjack, Sports Betting and the Stock Market*](https://gwern.net/doc/statistics/decision/2006-thorp.pdf) (2006)
- Books (figures cross-checked via the sites above): Schlesinger *Blackjack Attack* (I18 p.213 BJA3, Fab 4, SCORE, N0), Griffin *The Theory of Blackjack* (BC/PE/IC), Wong *Professional Blackjack* (truncation convention, Halves), Vancura & Fuchs *Knock-Out Blackjack* (IRC/key/pivot), Snyder *Blackbelt in Blackjack* (Red 7).

*Confidence note: this environment's network policy blocked full-page
fetches, so figures were verified via search-result extracts from the
sources above plus standard literature values rather than full-text reads.
The I18/Fab-4 indices, KO parameters, rule-variation costs, and BC/PE/IC
table each matched across at least two independent sources; single-source
figures (live-dealer $/hr simulation) are marked by attribution.*
