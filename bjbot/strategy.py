"""Basic strategy (multi-deck) with Illustrious 18 + Fab 4 true-count deviations.

Actions: HIT, STAND, DOUBLE, SPLIT, SURRENDER, INSURANCE (advice only).
Rules are configurable: dealer hits/stands soft 17, double-after-split,
late surrender.
"""

from dataclasses import dataclass

from .counter import normalize_rank

HIT = "HIT"
STAND = "STAND"
DOUBLE = "DOUBLE"
SPLIT = "SPLIT"
SURRENDER = "SURRENDER"

CARD_VALUE = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "T": 10, "J": 10, "Q": 10, "K": 10,
}


@dataclass
class Rules:
    dealer_hits_soft_17: bool = True   # H17 (most live tables); False = S17
    double_after_split: bool = True
    late_surrender: bool = True
    can_double: bool = True            # False after 3+ cards on most tables
    insurance_tc: float = 3.0          # take insurance at TC >= +3 (Hi-Lo)


def hand_value(ranks: list[str]) -> tuple[int, bool]:
    """Return (best total, is_soft). Aces count 11 then downgrade as needed."""
    total = sum(CARD_VALUE[r] for r in ranks)
    aces = sum(1 for r in ranks if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def _up(dealer: str) -> int:
    """Dealer upcard as a comparable number: 2-10, ace = 11."""
    return CARD_VALUE[dealer]


# --- Deviations -------------------------------------------------------------
# Illustrious 18 + Fab 4, Hi-Lo indices for shoe games.
# Each entry: (kind, player_key, dealer_up, tc_threshold, at_or_above, below)
# kind: "hard" (player_key = total), "pair" (player_key = rank), "surrender".
# below=None means "fall through to basic strategy".
DEVIATIONS = [
    # Fab 4 surrenders (checked first; only apply when surrender is allowed
    # and the hand is the first two cards).
    ("surrender", 14, 10, 3.0, SURRENDER, None),
    ("surrender", 15, 10, 0.0, SURRENDER, HIT),   # below 0: hit instead
    ("surrender", 15, 9, 2.0, SURRENDER, None),
    ("surrender", 15, 11, 1.0, SURRENDER, None),
    # Illustrious 18
    ("hard", 16, 10, 0.0, STAND, HIT),
    ("hard", 16, 9, 5.0, STAND, None),
    ("hard", 15, 10, 4.0, STAND, None),
    ("pair", "T", 5, 5.0, SPLIT, None),
    ("pair", "T", 6, 4.0, SPLIT, None),
    ("hard", 10, 10, 4.0, DOUBLE, None),
    ("hard", 10, 11, 4.0, DOUBLE, None),
    ("hard", 12, 2, 3.0, STAND, None),
    ("hard", 12, 3, 2.0, STAND, None),
    ("hard", 12, 4, 0.0, STAND, HIT),
    ("hard", 12, 5, -2.0, STAND, HIT),
    ("hard", 12, 6, -1.0, STAND, HIT),
    ("hard", 13, 2, -1.0, STAND, HIT),
    ("hard", 13, 3, -2.0, STAND, HIT),
    ("hard", 11, 11, 1.0, DOUBLE, None),
    ("hard", 9, 2, 1.0, DOUBLE, None),
    ("hard", 9, 7, 3.0, DOUBLE, None),
]


def _deviation(player: list[str], total: int, is_soft: bool, is_pair: bool,
               dealer: str, tc: float, rules: Rules) -> str | None:
    up = _up(dealer)
    first_two = len(player) == 2
    for kind, key, dev_up, threshold, above, below in DEVIATIONS:
        if dev_up != up:
            continue
        if kind == "surrender":
            if not (rules.late_surrender and first_two) or is_soft or is_pair:
                continue
            if key != total:
                continue
        elif kind == "pair":
            if not (is_pair and first_two) or normalize_rank(player[0]) != key:
                continue
        else:  # hard
            if is_soft or key != total:
                continue
            if above == DOUBLE and not (first_two and rules.can_double):
                continue
            # 15/16 vs 9/10/A: when late surrender is available on the first
            # two cards, the surrender plays above take precedence.
            if (above == STAND and total in (15, 16) and up >= 9
                    and rules.late_surrender and first_two):
                continue
        action = above if tc >= threshold else below
        if action is not None:
            return action
    return None


# --- Basic strategy ---------------------------------------------------------

def _pair_action(rank: str, up: int, rules: Rules) -> str | None:
    """Return SPLIT or None (None = play as the equivalent hard/soft total)."""
    das = rules.double_after_split
    if rank == "A":
        return SPLIT
    if rank in ("T", "J", "Q", "K"):
        return None  # never split tens in basic strategy (deviations may)
    if rank == "9":
        return SPLIT if up in (2, 3, 4, 5, 6, 8, 9) else None
    if rank == "8":
        return SPLIT
    if rank == "7":
        return SPLIT if up <= 7 else None
    if rank == "6":
        return SPLIT if (2 if das else 3) <= up <= 6 else None
    if rank == "5":
        return None  # play as hard 10
    if rank == "4":
        return SPLIT if das and up in (5, 6) else None
    # 2s and 3s
    return SPLIT if (2 if das else 4) <= up <= 7 else None


def _soft_action(total: int, up: int, rules: Rules, first_two: bool) -> str:
    can_double = first_two and rules.can_double
    if total >= 20:
        return STAND
    if total == 19:  # A8: double vs 6 in H17
        if rules.dealer_hits_soft_17 and up == 6 and can_double:
            return DOUBLE
        return STAND
    if total == 18:  # A7
        low = 2 if rules.dealer_hits_soft_17 else 3
        if low <= up <= 6 and can_double:
            return DOUBLE
        if up in (2, 3, 4, 5, 6, 7, 8):
            return STAND
        return HIT
    if total == 17:  # A6
        return DOUBLE if 3 <= up <= 6 and can_double else HIT
    if total in (15, 16):  # A4/A5
        return DOUBLE if 4 <= up <= 6 and can_double else HIT
    # A2/A3
    return DOUBLE if 5 <= up <= 6 and can_double else HIT


def _hard_action(total: int, up: int, rules: Rules, first_two: bool) -> str:
    can_double = first_two and rules.can_double
    if total >= 17:
        if (rules.late_surrender and first_two and total == 17
                and up == 11 and rules.dealer_hits_soft_17):
            return SURRENDER
        return STAND
    if total >= 13:
        if rules.late_surrender and first_two:
            if total == 16 and up in (9, 10, 11):
                return SURRENDER
            if total == 15 and (up == 10 or (up == 11 and rules.dealer_hits_soft_17)):
                return SURRENDER
        return STAND if up <= 6 else HIT
    if total == 12:
        return STAND if 4 <= up <= 6 else HIT
    if total == 11:
        if can_double and (up <= 10 or rules.dealer_hits_soft_17):
            return DOUBLE
        return HIT
    if total == 10:
        return DOUBLE if up <= 9 and can_double else HIT
    if total == 9:
        return DOUBLE if 3 <= up <= 6 and can_double else HIT
    return HIT


def recommend(player_cards: list[str], dealer_up: str, true_count: float = 0.0,
              rules: Rules | None = None) -> dict:
    """Best move for the hand. Returns {action, reason, insurance, total, soft}."""
    rules = rules or Rules()
    player = [normalize_rank(r) for r in player_cards]
    dealer = normalize_rank(dealer_up)
    up = _up(dealer)
    total, is_soft = hand_value(player)
    first_two = len(player) == 2
    is_pair = first_two and CARD_VALUE[player[0]] == CARD_VALUE[player[1]]

    insurance = up == 11 and true_count >= rules.insurance_tc

    if total > 21:
        return {"action": "BUST", "reason": "hand is over 21", "insurance": False,
                "total": total, "soft": is_soft}
    if first_two and total == 21:
        return {"action": STAND, "reason": "blackjack!", "insurance": insurance,
                "total": total, "soft": is_soft}

    dev = _deviation(player, total, is_soft, is_pair, dealer, true_count, rules)
    if dev is not None:
        return {"action": dev,
                "reason": f"count deviation (TC {true_count:+.1f})",
                "insurance": insurance, "total": total, "soft": is_soft}

    if is_pair:
        pair = _pair_action(player[0], up, rules)
        if pair is not None:
            return {"action": pair, "reason": "basic strategy (pair)",
                    "insurance": insurance, "total": total, "soft": is_soft}

    if is_soft:
        action = _soft_action(total, up, rules, first_two)
    else:
        action = _hard_action(total, up, rules, first_two)
    return {"action": action, "reason": "basic strategy",
            "insurance": insurance, "total": total, "soft": is_soft}
