# Is Stake live blackjack beatable by counting? — the simulation verdict

**Short answer: no, not meaningfully.** The bot works and the math is real,
but Stake's live blackjack is built so that counting can't get traction. At
its conditions you make roughly **$0.40/hour**, and you'd need on the order
of **5,000 hours of play** just to be statistically confident you're ahead
of variance rather than running lucky. It is, for practical purposes, a
break-even game you cannot grind a profit from.

This is not a tooling problem — a perfect counter (human or bot) hits the
same wall. The wall is **penetration**.

## The game (from the table screen + Evolution's standard live blackjack)

- 8 decks, dealer **stands on soft 17** (screen: "dealer must stand on 17"),
  blackjack pays **3:2**, insurance 2:1, double after split, **no surrender**.
- Off-the-top house edge with perfect basic strategy: **≈ 0.44%**.
- **Penetration ≈ 50%** — the shoe is shuffled with about 4 of 8 decks still
  behind the cut card. This is the decisive number, and it's the one Stake
  (via Evolution) sets against you. The high-count situations that make
  counting pay only develop *deep* in the shoe — exactly the part you never
  get to see here.

## What the simulation did

`bjbot/simulator.py` deals real shoes card-by-card, plays every hand with
basic strategy + Hi-Lo index deviations, **Wongs** (sits out and bets $0
below the entry true count), and ramps the bet with the count above it. Each
scenario is **3,000,000 rounds**. It reports the numbers that actually decide
whether a game is worth playing, not just "edge".

Reproduce any row:

```bash
python main.py sim --decks 8 --pen 0.5 --min-bet 5 --max-bet 100 \
                   --enter-tc 2 --rounds-per-hour 50 --rounds 3000000
```

### Engine validation

Flat-betting basic strategy with **no counting** returned **−0.51%** edge on
money wagered — within a rounding of the ≈−0.44% textbook figure for these
rules (the engine is ~0.05–0.10% conservative, i.e. it slightly *understates*
the counting edge, so the real EV numbers are marginally better than shown —
not enough to change any conclusion). Per-hand outcomes came out
**win 43.3% / push 8.7% / loss 48.0%**, the known basic-strategy distribution.

## Results

| Game | Pen | Play % | Edge on action | **EV/hr** | N0 (rounds) | RoR |
|---|---|---|---|---|---|---|
| No count, flat $5 | 50% | 100% | −0.51% | −$1.52 | — | 100% |
| **Stake $5–$100, wong TC+2** | **50%** | 7.5% | +0.96% | **+$0.40** | 270,000 | 0.01% |
| Stake $5–$100, wong TC+3 | 50% | 2.4% | +1.01% | +$0.19 | 887,000 | 0.3% |
| Stake rules, 60% pen | 60% | 9.9% | +1.11% | +$0.70 | 165,000 | 0.02% |
| Stake rules, 66% pen | 66% | 11.4% | +1.35% | +$1.06 | 102,000 | 0.01% |
| Stake rules, 75% pen | 75% | 13.7% | +1.55% | +$1.68 | 70,000 | 0.02% |
| **Real physical 6-deck, 75% pen, $10–$300, 80/hr** | 75% | 20.4% | +1.81% | **+$15.35** | 38,000 | 1.6% |

(EV/hr for Stake rows assumes 50 rounds/hour — live-dealer online is slow.)

## What the numbers say

1. **You never win more than half your hands.** Across every scenario the
   win rate sits at ~43–44%. Counting does not flip individual hands in your
   favor; it lets you bet more when the *remaining* cards favor you. A target
   of ">50% per hand" is unreachable by anyone, ever. The correct target is
   positive EV/hour at tolerable risk.

2. **Counting does make the edge positive** — at Stake's 50% pen you go from
   −0.51% (house) to +0.96% on the money you actually put out. The bot is
   doing its job. The problem is what that edge is worth in dollars.

3. **~$0.40/hour.** Because you can only bet on ~7% of rounds and the average
   bet is small, +0.96% on action becomes 40 cents an hour. Wonging harder
   (TC+3) raises the *percentage* but lowers the *dollars*, because you play
   even less. There is no spread/threshold setting that rescues this.

4. **N0 = 270,000 rounds is the real killer.** N0 is how many rounds it takes
   for your expected win to equal one standard deviation of swing. At 50
   rounds/hour that's **~5,400 hours**. Below that horizon your results are
   dominated by luck, not skill. You would swing hundreds of dollars up and
   down for months to net a few dollars of "expectation".

5. **Penetration is the entire game.** Going 50% → 75% pen roughly quadruples
   EV/hr — but even a 75% Stake game (which Stake does **not** offer) is only
   $1.68/hr. The contrast row shows what a genuinely beatable game looks like:
   deep penetration, bigger bets, faster play → **$15/hr** — about 40× Stake,
   and even that needs a $15k bankroll and carries real risk of ruin.

## Bottom line

The bot is correct and the flag fires when it should. But at Stake's ~50%
penetration the edge is real yet economically worthless: **~$0.40/hour with a
five-figure hour-count before you can even trust the result.** Any variance
you see over a session — up or down — is noise, not skill paying off.

If the goal is to make money from counting, the only thing that changes the
verdict is **penetration**, and that's a property of the *game*, not the tool
— you'd need a deep-dealt shoe (75%+), which means physical shoe games, not
Evolution live. Use this repo as an analysis tool: point `python main.py sim`
at any game's rules/penetration/spread before you ever risk a dollar, and let
the EV/hr and N0 columns tell you whether it's worth sitting down.
