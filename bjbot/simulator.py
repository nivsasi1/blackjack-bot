"""Monte-Carlo blackjack simulator — measures the real EV of a counting +
Wonging strategy under a given rule set, penetration, and bet spread.

It deals full shoes, plays every hand with basic strategy + Hi-Lo index
deviations, sits out (bets nothing) below the Wong-in true count, and ramps
the bet with the count above it. It reports the numbers that actually decide
whether a game is beatable:

  - per-hand win / push / loss rates (to kill the ">50% per hand" myth)
  - edge per unit wagered, and average edge per round
  - EV per 100 rounds and EV per hour (given a rounds/hour figure)
  - standard deviation per round, N0 (rounds to overcome variance), and
    risk of ruin for a given bankroll.

Pure Python, no dependencies. ~1-2M rounds/minute.
"""

import math
import random
from dataclasses import dataclass, field

from .counter import CardCounter, estimate_base_house_edge
from .strategy import CARD_VALUE, DOUBLE, HIT, SPLIT, STAND, SURRENDER, Rules, hand_value, recommend

# One full deck's worth of ranks (T covers all four ten-valued cards' *count*
# tag, but for play we need J/Q/K to be distinct 10s — they play identically,
# so a single "T" rank with weight 4x ten-value is correct for both play and
# the Hi-Lo count).
_ONE_DECK = (["A", "2", "3", "4", "5", "6", "7", "8", "9"] * 4
             + ["T"] * 16)  # 36 non-tens + 16 tens (T=J=Q=K) = 52 cards


@dataclass
class SimRules(Rules):
    blackjack_pays: float = 1.5      # 3:2 = 1.5, 6:5 = 1.2
    max_split_hands: int = 4
    resplit_aces: bool = False


@dataclass
class SimConfig:
    decks: int = 8
    penetration: float = 0.5         # fraction of shoe dealt before shuffle
    enter_tc: float = 2.0            # Wong in at/above this true count
    min_bet: float = 5.0             # bet at/below enter_tc when we do play
    max_bet: float = 100.0           # cap of the ramp
    bet_per_tc: float = 5.0          # add this many $ of bet per TC above enter
    wong: bool = True                # sit out (bet 0) below enter_tc
    flat: bool = False               # ignore ramp, flat-bet min_bet when in
    rounds: int = 2_000_000
    rounds_per_hour: float = 60.0    # live-dealer online is slow (~40-70)
    bankroll: float = 10_000.0
    seed: int = 12345
    rules: SimRules = field(default_factory=SimRules)


class _Shoe:
    def __init__(self, decks: int, penetration: float, rng: random.Random):
        self.rng = rng
        self.decks = decks
        self.cut = int(52 * decks * penetration)
        self.cards: list[str] = []
        self.dealt = 0
        self._shuffle()

    def _shuffle(self):
        self.cards = _ONE_DECK * self.decks
        self.rng.shuffle(self.cards)
        self.dealt = 0

    def needs_shuffle(self) -> bool:
        return self.dealt >= self.cut

    def draw(self) -> str:
        c = self.cards[self.dealt]
        self.dealt += 1
        return c


def _bet_for(counter: CardCounter, cfg: SimConfig) -> float:
    """Bet size for the upcoming round given the current count."""
    tc = counter.betting_count
    if cfg.wong and tc < cfg.enter_tc:
        return 0.0
    if cfg.flat:
        return cfg.min_bet
    units_over = max(0.0, tc - cfg.enter_tc)
    bet = cfg.min_bet + units_over * cfg.bet_per_tc
    return min(bet, cfg.max_bet)


def _play_player_hand(cards, shoe, counter, dealer_up, tc, rules, state,
                      from_split=False):
    """Play one player hand to completion. Returns list of (cards, bet_mult,
    surrendered) — a list because splits create multiple hands.

    `state` is {"hands": n}: the number of hands currently in play from this
    seat, used to enforce the table's max-split-hands cap. `from_split` marks
    a hand that came from a split (no surrender; double only if DAS).
    """
    while True:
        move = recommend(cards, dealer_up, tc, rules, from_split=from_split)["action"]
        # recommend() only emits SURRENDER on an eligible first-two-card,
        # non-split hand, so this never fires post-split.
        if move == SURRENDER:
            return [(cards, 0.5, True)]
        can_split = (move == SPLIT and len(cards) == 2
                     and CARD_VALUE[cards[0]] == CARD_VALUE[cards[1]]
                     and state["hands"] < rules.max_split_hands)
        if can_split:
            state["hands"] += 1          # one hand becomes two
            results = []
            is_aces = cards[0] == "A"
            for c in cards:
                nc = shoe.draw(); counter.see(nc)
                hand = [c, nc]
                if is_aces and not rules.resplit_aces:
                    results.append((hand, 1.0, False))  # aces: one card, done
                else:
                    results.extend(_play_player_hand(
                        hand, shoe, counter, dealer_up, tc, rules, state,
                        from_split=True))
            return results
        if move == DOUBLE and len(cards) == 2:
            nc = shoe.draw(); counter.see(nc)
            cards.append(nc)
            return [(cards, 2.0, False)]
        if move == HIT:
            nc = shoe.draw(); counter.see(nc)
            cards.append(nc)
            if hand_value(cards)[0] > 21:
                return [(cards, 1.0, False)]
            continue
        return [(cards, 1.0, False)]  # STAND


def _play_dealer(cards, shoe, counter, rules):
    while True:
        total, soft = hand_value(cards)
        if total < 17 or (total == 17 and soft and rules.dealer_hits_soft_17):
            nc = shoe.draw(); counter.see(nc)
            cards.append(nc)
        else:
            return total


def _round_outcome(shoe, counter, cfg) -> float:
    """Play one round for our single seat. Returns net units (per 1 unit bet)
    that our bet won/lost, using the count BEFORE the round for the decision.
    Feeds every exposed card to the counter. Returns net as a multiple of the
    base bet (so caller multiplies by actual $ bet)."""
    rules = cfg.rules
    tc = counter.true_count

    # deal: player two, dealer up + hole
    p = [shoe.draw(), shoe.draw()]
    d_up = shoe.draw()
    d_hole = shoe.draw()
    counter.see(p[0]); counter.see(p[1]); counter.see(d_up)

    p_total, _ = hand_value(p)
    d_total0, _ = hand_value([d_up, d_hole])
    player_bj = p_total == 21
    dealer_bj = d_total0 == 21

    if player_bj or dealer_bj:
        counter.see(d_hole)  # hole revealed immediately on a natural
        if player_bj and dealer_bj:
            return 0.0
        if player_bj:
            return cfg.rules.blackjack_pays
        return -1.0

    hands = _play_player_hand(p, shoe, counter, d_up, tc, rules, {"hands": 1})
    counter.see(d_hole)

    if hands[0][2]:  # surrendered
        return -0.5

    all_bust = all(hand_value(h)[0] > 21 for h, _m, _s in hands)
    if all_bust:
        return -sum(m for _h, m, _s in hands)

    d_total = _play_dealer([d_up, d_hole], shoe, counter, rules)

    net = 0.0
    for h, mult, _s in hands:
        pt = hand_value(h)[0]
        if pt > 21:
            net -= mult
        elif d_total > 21 or pt > d_total:
            net += mult
        elif pt < d_total:
            net -= mult
    return net


def run_sim(cfg: SimConfig) -> dict:
    rng = random.Random(cfg.seed)
    base_edge = estimate_base_house_edge(
        decks=cfg.decks,
        dealer_hits_soft_17=cfg.rules.dealer_hits_soft_17,
        double_after_split=cfg.rules.double_after_split,
        late_surrender=cfg.rules.late_surrender,
        blackjack_pays_65=(cfg.rules.blackjack_pays < 1.5),
    )
    counter = CardCounter(decks=cfg.decks, base_house_edge=base_edge,
                          enter_tc=cfg.enter_tc, edge_per_tc=0.005)
    shoe = _Shoe(cfg.decks, cfg.penetration, rng)

    net_sum = 0.0          # total $ won/lost
    net_sq = 0.0           # sum of squared per-round $ result (variance)
    wagered = 0.0          # total $ put at risk
    played = 0             # rounds we actually bet on
    wins = losses = pushes = 0

    for _ in range(cfg.rounds):
        if shoe.needs_shuffle():
            shoe._shuffle()
            counter.new_shoe()
        bet = _bet_for(counter, cfg)
        if bet <= 0:
            # sit out but still watch: consume/count a round's cards
            _round_outcome(shoe, counter, cfg)
            continue
        net_mult = _round_outcome(shoe, counter, cfg)
        result = net_mult * bet
        net_sum += result
        net_sq += result * result
        wagered += bet
        played += 1
        if net_mult > 0:
            wins += 1
        elif net_mult < 0:
            losses += 1
        else:
            pushes += 1

    dealt = cfg.rounds
    ev_per_played = net_sum / played if played else 0.0
    var_per_played = (net_sq / played - ev_per_played ** 2) if played else 0.0
    sd_per_played = math.sqrt(max(var_per_played, 0.0))
    edge_on_action = net_sum / wagered if wagered else 0.0
    ev_per_dealt = net_sum / dealt

    # Risk of ruin (lifetime, fixed-strategy exponential approximation):
    #   RoR = exp(-2 * bankroll * EV_per_round / Var_per_round)
    # using per-DEALT-round EV and variance (variance accrues even when the
    # per-round result is 0 for sat-out rounds, but those contribute 0 to both
    # sums, so per-played scaled by play-rate is equivalent; use per-dealt).
    var_per_dealt = net_sq / dealt - ev_per_dealt ** 2
    if var_per_dealt > 0 and ev_per_dealt > 0:
        ror = math.exp(-2 * cfg.bankroll * ev_per_dealt / var_per_dealt)
        n0 = var_per_dealt / (ev_per_dealt ** 2)  # rounds to 1 SD = EV
    else:
        ror = 1.0
        n0 = float("inf")

    rounds_per_hr = cfg.rounds_per_hour
    return {
        "dealt_rounds": dealt,
        "played_rounds": played,
        "play_rate_pct": round(100 * played / dealt, 2),
        "win_pct": round(100 * wins / played, 2) if played else 0,
        "push_pct": round(100 * pushes / played, 2) if played else 0,
        "loss_pct": round(100 * losses / played, 2) if played else 0,
        "avg_bet": round(wagered / played, 2) if played else 0,
        "edge_on_action_pct": round(100 * edge_on_action, 3),
        "ev_per_dealt_round": round(ev_per_dealt, 4),
        "ev_per_100_dealt": round(100 * ev_per_dealt, 3),
        "ev_per_hour": round(ev_per_dealt * rounds_per_hr, 2),
        "sd_per_played_round": round(sd_per_played, 3),
        "n0_rounds": round(n0) if math.isfinite(n0) else None,
        "risk_of_ruin_pct": round(100 * ror, 2),
        "net_total": round(net_sum, 2),
        "hours_simulated": round(dealt / rounds_per_hr, 1),
        "base_house_edge_pct": round(100 * base_edge, 3),
    }
