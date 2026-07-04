"""Sanity tests for the counting and strategy engines (no vision deps needed).

Run:  python test_bjbot.py
"""

from bjbot.counter import CardCounter, SYSTEMS, estimate_base_house_edge
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

# --- multi-system counting ---------------------------------------------------
# KO (unbalanced): IRC = 4 - 4*decks, 7 counts +1, pivot RC +4 == TC +4
ko = CardCounter(decks=6, system_name="ko")
check(ko.running_count, -20.0, "KO 6-deck IRC is -20")
check(CardCounter(decks=8, system_name="ko").running_count, -28.0, "KO 8-deck IRC is -28")
ko.see("7")
check(ko.running_count, -19.0, "KO counts 7 as +1")
check(ko.key_count, -4, "KO 6-deck key count is -4")
check(ko.should_enter, False, "KO below key count -> wait")
for _ in range(16):  # +16 more brings RC to -3, past the key count
    ko.see("2")
check(ko.running_count, -3.0, "KO RC after low run")
check(ko.should_enter, True, "KO at/above key count -> enter")
check(SYSTEMS["ko"].pivot_rc(6), 4, "KO pivot RC is +4 at any deck count")
check(SYSTEMS["ko"].pivot_rc(8), 4, "KO pivot RC is +4 (8 decks too)")

# KO pivot == Hi-Lo TC +4 regardless of shoe depth
ko2 = CardCounter(decks=6, system_name="ko")
for _ in range(24):  # 24 low cards: RC -20 -> +4 == pivot
    ko2.see("3")
check(round(ko2.true_count, 2), 4.0, "KO at pivot -> TC-equivalent +4")

# Red 7: IRC = -2*decks, color-blind 7 = +0.5, r7/b7 exact
r7 = CardCounter(decks=6, system_name="red-7")
check(r7.running_count, -12.0, "Red 7 6-deck IRC is -12")
r7.see("7")
check(r7.running_count, -11.5, "color-blind 7 counts +0.5")
r7.see("r7")
check(r7.running_count, -10.5, "red seven counts +1")
r7.see("b7")
check(r7.running_count, -10.5, "black seven counts 0")
check(r7.undo(), "7", "undo returns the rank for b7")
check(r7.running_count, -10.5, "undo of black 7 keeps RC")
check(SYSTEMS["red-7"].pivot_rc(6), 0, "Red 7 pivot RC is 0")
check(CardCounter(decks=8, system_name="red-7").key_count, 0.0,
      "Red 7 key count falls back to pivot (TC+2) = RC 0")

# Ace-neutral systems: ace side count adjusts betting count only
ho = CardCounter(decks=6, system_name="hi-opt-1")
ho.see("A")
check(ho.running_count, 0.0, "Hi-Opt I: ace tag is 0")
check(ho.betting_count < ho.true_count, True,
      "ace gone -> ace-poor -> betting count below playing count")
check(SYSTEMS["hi-opt-2"].tags["4"], 2, "Hi-Opt II: 4 counts +2")
check(SYSTEMS["omega-2"].tags["9"], -1, "Omega II: 9 counts -1")
check(SYSTEMS["zen"].tags["A"], -1, "Zen counts the ace")
check(SYSTEMS["wong-halves"].tags["5"], 1.5, "Wong Halves: 5 counts +1.5")
check(SYSTEMS["wong-halves"].tags["2"], 0.5, "Wong Halves: 2 counts +0.5")

# TC display conventions: RC -2 with exactly 4 decks remaining -> -0.5
tcc = CardCounter(decks=6, half_deck_divisor=False)
for _ in range(104):  # 2 decks of 8s: RC stays 0, 4 decks remain
    tcc.see("8")
tcc.see("K")
tcc.see("K")  # RC -2, ~3.96 decks left; use half_deck path off for exactness
tcc.running_count = -2.0
tcc.cards_seen = 104
check(tcc.true_count, -0.5, "exact TC -0.5")
tcc.tc_method = "floor"
check(tcc.displayed_tc, -1.0, "floor(-0.5) = -1")
tcc.tc_method = "trunc"
check(tcc.displayed_tc, 0.0, "trunc(-0.5) = 0")

# Rule-based house edge anchors (Wizard of Odds figures)
check(round(estimate_base_house_edge(6, True, True, False), 4), 0.0064,
      "6D H17 DAS noLS = 0.64%")
check(round(estimate_base_house_edge(6, False, True, False), 4), 0.0042,
      "S17 is worth -0.22%")
check(estimate_base_house_edge(6, True, True, False, blackjack_pays_65=True)
      > 0.019, True, "6:5 adds +1.39%")

# Kelly sizing: TC +3 with 0.5% base -> ~1% edge; half-Kelly on 10k ~ 38
kb = CardCounter(decks=8, bankroll=10000, kelly_divisor=2.0,
                 base_house_edge=0.005, edge_per_tc=0.005)
kb.running_count = 24.0
kb.cards_seen = 0  # 8 decks remain -> TC +3
check(round(kb.true_count, 2), 3.0, "kelly setup TC +3")
check(35 < kb.kelly_bet() < 42, True, "half-Kelly ~ bankroll*edge/1.32/2")
kb.running_count = 0.0
check(kb.kelly_bet(), 0.0, "no edge -> Kelly bet 0")

# --- split-hand context (bugs 1-3 fixes) ------------------------------------
# A split hand is never allowed to surrender (opening hand would).
check(recommend(["T", "6"], "10", -1.0, R, from_split=True)["action"], HIT,
      "split 16 v 10 at TC-1 hits, not surrender")
check(recommend(["T", "6"], "10", 0.0, R, from_split=True)["action"], STAND,
      "split 16 v 10 at TC0 stands (I18 dev applies), still not surrender")
check(recommend(["T", "5"], "10", 0.0, R, from_split=True)["action"], HIT,
      "split 15 v 10 hits (no post-split surrender)")
# ...and it can only double when DAS is offered.
das = Rules(double_after_split=True)
no_das = Rules(double_after_split=False)
check(recommend(["5", "6"], "6", 0.0, das, from_split=True)["action"], DOUBLE,
      "split 11 v 6 doubles when DAS on")
check(recommend(["5", "6"], "6", 0.0, no_das, from_split=True)["action"], HIT,
      "split 11 v 6 hits when DAS off")
# A count-deviation double (9 v 2 @ TC+1) also respects DAS post-split.
check(recommend(["4", "5"], "2", 1.0, no_das, from_split=True)["action"], HIT,
      "split 9 v 2 deviation double suppressed when DAS off")
check(recommend(["4", "5"], "2", 1.0, das, from_split=True)["action"], DOUBLE,
      "split 9 v 2 deviation double allowed when DAS on")
# Split hand reaching 21 is not a blackjack (stands, pays even later).
check(recommend(["A", "T"], "9", 0.0, R, from_split=True)["action"], STAND,
      "split A+T=21 stands and is not flagged blackjack")
# Opening-hand behaviour is unchanged.
check(recommend(["T", "6"], "10", 0.0, R)["action"], SURRENDER,
      "opening 16 v 10 still surrenders")

# --- simulator: resplit cap + validation ------------------------------------
from bjbot.simulator import SimConfig, SimRules, _play_player_hand, run_sim


class _FixedShoe:
    def __init__(self, cards):
        self.cards = list(cards)
        self.dealt = 0

    def draw(self):
        c = self.cards[self.dealt]
        self.dealt += 1
        return c


class _NullCounter:
    def see(self, rank):
        pass


# Feed an endless stream of 8s to a pair of 8s: without a cap this splits
# forever; the cap must hold total hands to max_split_hands (4).
rules4 = SimRules(max_split_hands=4, double_after_split=True)
state = {"hands": 1}
hands = _play_player_hand(["8", "8"], _FixedShoe(["8"] * 40), _NullCounter(),
                          "T", 0.0, rules4, state)
check(state["hands"] <= 4, True, "resplit cap holds at 4 hands")
check(len(hands) <= 4, True, "no more than 4 hands returned from splitting")

# Simulator smoke: basic strategy EV should be within noise of the house edge.
val = run_sim(SimConfig(decks=8, penetration=0.5, wong=False, flat=True,
                        min_bet=5, max_bet=5, rounds=120000,
                        rules=SimRules(dealer_hits_soft_17=False)))
check(-1.0 < val["edge_on_action_pct"] < 0.2, True,
      "flat basic-strategy edge lands near the house edge")
check(41 < val["win_pct"] < 46, True, "win rate ~43% (never >50%)")

print(f"all {PASSED} checks passed")
