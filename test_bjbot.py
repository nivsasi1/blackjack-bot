"""Sanity tests for the counting and strategy engines (no vision deps needed).

Run:  python test_bjbot.py
"""

from bjbot.counter import CardCounter
from bjbot.strategy import DOUBLE, HIT, SPLIT, STAND, SURRENDER, Rules, recommend

PASSED = 0


def check(actual, expected, label):
    global PASSED
    assert actual == expected, f"{label}: expected {expected}, got {actual}"
    PASSED += 1


# --- counter ---------------------------------------------------------------
c = CardCounter(decks=8)
for r in ["2", "3", "4", "5", "6"]:   # +5
    c.see(r)
for r in ["K", "A"]:                  # -2
    c.see(r)
for r in ["7", "8", "9"]:             # 0
    c.see(r)
check(c.running_count, 3, "running count")
check(c.cards_seen, 10, "cards seen")
check(round(c.decks_remaining, 3), round(8 - 10 / 52, 3), "decks remaining")
check(c.undo(), "9", "undo returns last rank")
check(c.running_count, 3, "undo of 0-value card keeps RC")
c.see("10")
check(c.running_count, 2, "'10' normalizes to T (-1)")

hot = CardCounter(decks=8)
for _ in range(52):                   # a full deck of low cards: RC +52... use 20
    pass
for r in ["2"] * 21:
    hot.see(r)
check(hot.running_count, 21, "hot RC")
check(hot.true_count > 2.0, True, "hot shoe TC > 2")
check(hot.should_enter, True, "enter flag on hot shoe")
check(hot.player_edge > 0, True, "positive edge on hot shoe")
neg = CardCounter(decks=8)
for r in ["K"] * 10:
    neg.see(r)
check(neg.should_enter, False, "no enter flag on cold shoe")

# --- basic strategy (H17, DAS, late surrender) -------------------------------
R = Rules()


def act(cards, up, tc=0.0, rules=R):
    return recommend(cards, up, tc, rules)["action"]


check(act(["T", "6"], "5"), STAND, "16 v 5 stands")
check(act(["T", "6"], "7"), HIT, "16 v 7 hits")
check(act(["T", "6"], "10"), SURRENDER, "16 v 10 surrenders (LS)")
check(act(["9", "7"], "9"), SURRENDER, "16 v 9 surrenders (LS)")
no_ls = Rules(late_surrender=False)
check(act(["T", "6"], "10", tc=-1.0, rules=no_ls), HIT, "16 v 10 hits below TC 0 (no LS)")
check(act(["T", "6"], "10", tc=0.0, rules=no_ls), STAND, "16 v 10 stands at TC>=0 (no LS)")
check(act(["5", "6"], "6"), DOUBLE, "11 v 6 doubles")
check(act(["5", "6"], "A"), DOUBLE, "11 v A doubles (H17)")
check(act(["5", "5"], "9"), DOUBLE, "5,5 plays as 10 — double v 9")
check(act(["5", "5"], "10"), HIT, "5,5 v 10 hits, never split")
check(act(["8", "8"], "10"), SPLIT, "always split 8s")
check(act(["A", "A"], "6"), SPLIT, "always split aces")
check(act(["9", "9"], "7"), STAND, "9,9 v 7 stands")
check(act(["9", "9"], "8"), SPLIT, "9,9 v 8 splits")
check(act(["A", "7"], "2"), DOUBLE, "A7 v 2 doubles (H17)")
check(act(["A", "7"], "9"), HIT, "A7 v 9 hits")
check(act(["A", "8"], "6"), DOUBLE, "A8 v 6 doubles (H17)")
check(act(["A", "8"], "5"), STAND, "A8 v 5 stands")
check(act(["7", "5"], "2"), HIT, "12 v 2 hits")
check(act(["7", "5"], "4"), STAND, "12 v 4 stands")
check(act(["T", "T"], "6"), STAND, "never split tens at TC 0")
check(act(["A", "K"], "6"), STAND, "blackjack stands")
check(act(["T", "4", "2"], "10"), STAND, "3-card 16 v 10 stands at TC 0 (I18)")

# --- deviations --------------------------------------------------------------
check(act(["T", "4", "2"], "10", tc=1.0), STAND, "multi-card 16 v 10 stands at TC>=0")
check(act(["T", "4", "2"], "10", tc=-1.0), HIT, "multi-card 16 v 10 hits below TC 0")
check(act(["T", "6"], "10", tc=5.0), SURRENDER, "first-two 16v10: LS still wins")
check(act(["T", "2"], "3", tc=2.5), STAND, "12 v 3 stands at TC>=2")
check(act(["T", "2"], "3", tc=1.0), HIT, "12 v 3 hits below TC 2")
check(act(["T", "2"], "2", tc=3.0), STAND, "12 v 2 stands at TC>=3")
check(act(["6", "4"], "10", tc=4.0), DOUBLE, "10 v 10 doubles at TC>=4")
check(act(["6", "4"], "10", tc=3.0), HIT, "10 v 10 hits below TC 4")
check(act(["T", "T"], "5", tc=5.0), SPLIT, "T,T v 5 splits at TC>=5")
check(act(["T", "T"], "6", tc=4.0), SPLIT, "T,T v 6 splits at TC>=4")
check(act(["T", "T"], "6", tc=3.9), STAND, "T,T v 6 stands below TC 4")
check(act(["7", "2"], "2", tc=1.0), DOUBLE, "9 v 2 doubles at TC>=1")
check(act(["7", "2"], "2", tc=0.0), HIT, "9 v 2 hits below TC 1")
check(act(["T", "3"], "2", tc=-1.0), STAND, "13 v 2 stands at TC>=-1")
check(act(["T", "3"], "2", tc=-2.0), HIT, "13 v 2 hits below TC -1")
check(act(["T", "2"], "4", tc=-0.5), HIT, "12 v 4 hits below TC 0")
check(act(["T", "5"], "10", tc=0.5), SURRENDER, "15 v 10 surrenders at TC>=0")
check(act(["T", "5"], "10", tc=-1.0), HIT, "15 v 10 hits below TC 0 (Fab4)")
check(act(["T", "4"], "10", tc=3.0), SURRENDER, "14 v 10 surrenders at TC>=3")
check(act(["T", "5"], "9", tc=2.0), SURRENDER, "15 v 9 surrenders at TC>=2")
check(act(["T", "5"], "A", tc=1.0), SURRENDER, "15 v A surrenders at TC>=1")
check(recommend(["9", "9"], "A", 3.5)["insurance"], True, "insurance at TC>=3")
check(recommend(["9", "9"], "A", 2.0)["insurance"], False, "no insurance below TC 3")

print(f"all {PASSED} checks passed")
