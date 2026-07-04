"""Card counting engine: multiple systems, true-count conversion, edge model.

Supports balanced systems (Hi-Lo, Hi-Opt I/II, Omega II, Zen, Wong Halves)
and unbalanced systems (KO, Red 7). Unbalanced systems start from a
deck-dependent Initial Running Count (IRC) and make decisions on the raw
running count against a *key count* (bet trigger) and *pivot* (max bet /
known TC-equivalent point) instead of dividing by decks remaining.

System quality metrics (from Griffin's "Theory of Blackjack" tables):
- BC (Betting Correlation): how well the count predicts when to bet big.
  What matters in shoe games.
- PE (Playing Efficiency): how well it drives strategy deviations. What
  matters in 1-2 deck games. ~0.70 is the practical ceiling for one number.
- IC (Insurance Correlation): how well it prices the insurance bet.

See docs/COUNTING.md for the research behind every number here.
"""

from dataclasses import dataclass, field

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]

# Per-hand variance of a blackjack round is ~1.32 (SD ~1.15 bets) — used for
# Kelly sizing. (Schlesinger, Blackjack Attack.)
HAND_VARIANCE = 1.32


@dataclass(frozen=True)
class CountSystem:
    name: str
    tags: dict            # rank -> tag value ('7' may be fractional for Red 7)
    level: int
    balanced: bool
    bc: float             # betting correlation
    pe: float             # playing efficiency
    ic: float             # insurance correlation
    ace_neutral: bool = False       # True -> ace side count improves betting
    imbalance_per_deck: int = 0     # tag sum of one full deck (unbalanced)
    pivot_tc: float = 0.0           # Hi-Lo-equivalent TC at the pivot point
    # RC that triggers "you have the edge, bet up", by number of decks
    key_counts: dict = field(default_factory=dict)

    def irc(self, decks: int) -> int:
        """Initial running count for a fresh shoe."""
        if self.balanced:
            return 0
        if self.name == "ko":
            return 4 - 4 * decks          # KO book: IRC = 4 - (4 x decks)
        return -self.imbalance_per_deck * decks  # Red 7: -2 x decks

    def pivot_rc(self, decks: int) -> int:
        """RC at which the shoe is exactly at pivot_tc regardless of depth."""
        return self.irc(decks) + self.imbalance_per_deck * decks


def _tags(spec: dict) -> dict:
    """Expand {'2-6': 1, 'T,J,Q,K,A': -1, ...} into per-rank tags."""
    order = "A23456789T"
    out = {}
    for key, val in spec.items():
        for part in key.split(","):
            if "-" in part and len(part) == 3:
                lo, hi = part[0], part[2]
                for r in order[order.index(lo):order.index(hi) + 1]:
                    out[r] = val
            else:
                out[part] = val
    for face in "JQK":
        out.setdefault(face, out.get("T", 0))
    return out


SYSTEMS = {
    # Balanced, level 1. The default: best all-round for shoe play.
    "hi-lo": CountSystem(
        "hi-lo", _tags({"2-6": 1, "7-9": 0, "T": -1, "A": -1}),
        level=1, balanced=True, bc=0.97, pe=0.51, ic=0.76),
    # Unbalanced level 1 — no TC division needed; IRC/key/pivot instead.
    "ko": CountSystem(
        "ko", _tags({"2-7": 1, "8-9": 0, "T": -1, "A": -1}),
        level=1, balanced=False, bc=0.98, pe=0.55, ic=0.78,
        imbalance_per_deck=4, pivot_tc=4.0,
        key_counts={1: 2, 2: 1, 4: -1, 6: -4, 8: -6}),
    # Unbalanced level 1 (Snyder). Only *red* sevens count +1; a color-blind
    # screen watcher counts every 7 as +0.5 (Snyder's own simplification).
    "red-7": CountSystem(
        "red-7", _tags({"2-6": 1, "7": 0.5, "8-9": 0, "T": -1, "A": -1}),
        level=1, balanced=False, bc=0.98, pe=0.54, ic=0.78,
        imbalance_per_deck=2, pivot_tc=2.0),
    # Balanced, ace-neutral level 1 — pair with an ace side count.
    "hi-opt-1": CountSystem(
        "hi-opt-1", _tags({"2": 0, "3-6": 1, "7-9": 0, "T": -1, "A": 0}),
        level=1, balanced=True, bc=0.88, pe=0.61, ic=0.85, ace_neutral=True),
    # Balanced, ace-neutral level 2.
    "hi-opt-2": CountSystem(
        "hi-opt-2", _tags({"2,3,6,7": 1, "4,5": 2, "8,9": 0, "T": -2, "A": 0}),
        level=2, balanced=True, bc=0.91, pe=0.67, ic=0.91, ace_neutral=True),
    # Balanced level 2 (Bryce Carlson).
    "omega-2": CountSystem(
        "omega-2", _tags({"2,3,7": 1, "4-6": 2, "8": 0, "9": -1, "T": -2, "A": 0}),
        level=2, balanced=True, bc=0.92, pe=0.67, ic=0.85, ace_neutral=True),
    # Balanced level 2 (Snyder) — counts the ace, no side count needed.
    "zen": CountSystem(
        "zen", _tags({"2,3,7": 1, "4-6": 2, "8,9": 0, "T": -2, "A": -1}),
        level=2, balanced=True, bc=0.96, pe=0.63, ic=0.85),
    # Balanced level 3 (Wong) — highest BC, fractional tags.
    "wong-halves": CountSystem(
        "wong-halves", _tags({"2,7": 0.5, "3,4,6": 1, "5": 1.5, "8": 0,
                              "9": -0.5, "T": -1, "A": -1}),
        level=3, balanced=True, bc=0.99, pe=0.56, ic=0.72),
}

HI_LO = SYSTEMS["hi-lo"].tags  # kept for backwards compatibility


def normalize_rank(raw: str) -> str:
    """Accept '10', 'k', 'King', 'ace' etc. and return the canonical rank."""
    s = raw.strip().upper()
    if s in ("10", "1O"):
        return "T"
    aliases = {"ACE": "A", "KING": "K", "QUEEN": "Q", "JACK": "J", "TEN": "T"}
    s = aliases.get(s, s)
    if s not in HI_LO:
        raise ValueError(f"unknown card rank: {raw!r}")
    return s


def estimate_base_house_edge(decks: int = 6, dealer_hits_soft_17: bool = True,
                             double_after_split: bool = True,
                             late_surrender: bool = False,
                             blackjack_pays_65: bool = False) -> float:
    """Approximate off-the-top house edge for a rule set (basic strategy).

    Anchored to Wizard-of-Odds figures: 6D H17 DAS noLS 3:2 = 0.64%;
    S17 is worth -0.22%, LS -0.08%, no-DAS +0.14%, 8 decks +0.02%,
    6:5 blackjack +1.39%. Positive = house edge.
    """
    edge = 0.0064
    if not dealer_hits_soft_17:
        edge -= 0.0022
    if late_surrender:
        edge -= 0.0008
    if not double_after_split:
        edge += 0.0014
    if decks >= 8:
        edge += 0.0002
    elif decks <= 2:
        edge -= 0.0019
    if blackjack_pays_65:
        edge += 0.0139
    return edge


@dataclass
class CardCounter:
    decks: int = 8
    system_name: str = "hi-lo"
    # Fraction of the shoe dealt before the cut card (used only for reporting).
    penetration: float = 0.5
    # Player edge gained per (Hi-Lo-equivalent) true count point, and the
    # off-the-top house edge. ~0.5%/TC is the standard shoe-game figure.
    edge_per_tc: float = 0.005
    base_house_edge: float = 0.005
    # Wong-in threshold: flag entry at this true count (balanced systems).
    # Unbalanced systems use their key count on the raw RC instead.
    enter_tc: float = 2.0
    # TC display convention: "exact" | "floor" | "round" | "trunc".
    # (For integer thresholds, floor(tc) >= idx  ===  tc >= idx, so this
    # affects display/training, not decisions.)
    tc_method: str = "exact"
    # Divide by decks remaining to the nearest half deck (common convention).
    half_deck_divisor: bool = True
    # Bankroll for Kelly bet sizing; kelly_divisor 2 = half-Kelly (usual).
    bankroll: float = 0.0
    kelly_divisor: float = 2.0

    running_count: float = 0.0
    cards_seen: int = 0
    aces_seen: int = 0
    history: list = field(default_factory=list)  # (rank, tag) pairs

    def __post_init__(self):
        if self.system_name not in SYSTEMS:
            raise ValueError(
                f"unknown system {self.system_name!r}; pick from "
                f"{', '.join(sorted(SYSTEMS))}")
        self.running_count = float(self.system.irc(self.decks))

    @property
    def system(self) -> CountSystem:
        return SYSTEMS[self.system_name]

    # -- feeding cards ------------------------------------------------------

    def see(self, rank: str) -> None:
        """Count one card. For Red 7, 'r7'/'b7' give exact red/black tags."""
        tag = None
        s = rank.strip().upper()
        if self.system_name == "red-7" and s in ("R7", "B7"):
            rank, tag = "7", (1.0 if s == "R7" else 0.0)
        rank = normalize_rank(rank)
        if tag is None:
            tag = self.system.tags[rank]
        self.running_count += tag
        self.cards_seen += 1
        if rank == "A":
            self.aces_seen += 1
        self.history.append((rank, tag))

    def undo(self) -> str | None:
        """Remove the most recently counted card (misdetection correction)."""
        if not self.history:
            return None
        rank, tag = self.history.pop()
        self.running_count -= tag
        self.cards_seen -= 1
        if rank == "A":
            self.aces_seen -= 1
        return rank

    def new_shoe(self) -> None:
        self.running_count = float(self.system.irc(self.decks))
        self.cards_seen = 0
        self.aces_seen = 0
        self.history.clear()

    # -- shoe state ---------------------------------------------------------

    @property
    def decks_remaining(self) -> float:
        remaining = self.decks - self.cards_seen / 52.0
        return max(remaining, 0.25)  # avoid divide-by-zero blowups at the end

    @property
    def _divisor(self) -> float:
        if self.half_deck_divisor:
            return max(round(self.decks_remaining * 2) / 2, 0.5)
        return self.decks_remaining

    @property
    def aces_remaining(self) -> int:
        return 4 * self.decks - self.aces_seen

    @property
    def excess_aces(self) -> float:
        """Aces remaining beyond the pro-rata share (positive = ace-rich)."""
        return self.aces_remaining - 4 * self.decks_remaining

    # -- counts -------------------------------------------------------------

    @property
    def true_count(self) -> float:
        """Hi-Lo-equivalent true count used for strategy indices and edge.

        Balanced: RC / decks remaining. Unbalanced: the count is exactly
        pivot_tc at the pivot RC at any depth, and drifts by
        (RC - pivot_rc) / decks_remaining around it.
        """
        if self.system.balanced:
            return self.running_count / self._divisor
        pivot = self.system.pivot_rc(self.decks)
        return (self.running_count - pivot) / self._divisor + self.system.pivot_tc

    @property
    def betting_count(self) -> float:
        """True count adjusted for betting: ace side count for ace-neutral
        systems (each excess ace is worth ~1 Hi-Lo point, ~2 at level 2)."""
        tc = self.true_count
        if self.system.ace_neutral:
            adj = self.excess_aces * (2 if self.system.level >= 2 else 1)
            tc = tc + adj / self._divisor
        return tc

    @property
    def displayed_tc(self) -> float:
        import math
        tc = self.true_count
        if self.tc_method == "floor":
            return float(math.floor(tc))
        if self.tc_method == "round":
            return float(round(tc))
        if self.tc_method == "trunc":
            return float(int(tc))
        return tc

    # -- decisions ----------------------------------------------------------

    @property
    def player_edge(self) -> float:
        """Approximate player edge for the next round (negative = house)."""
        return self.betting_count * self.edge_per_tc - self.base_house_edge

    @property
    def key_count(self) -> float | None:
        """Unbalanced systems: RC at which to start betting up."""
        if self.system.balanced:
            return None
        kc = self.system.key_counts.get(self.decks)
        if kc is not None:
            return kc
        # fall back to the RC where TC-equivalent hits enter_tc
        pivot = self.system.pivot_rc(self.decks)
        return pivot + (self.enter_tc - self.system.pivot_tc) * self._divisor

    @property
    def should_enter(self) -> bool:
        if self.system.balanced:
            return self.betting_count >= self.enter_tc
        return self.running_count >= self.key_count

    def bet_units(self, max_units: int = 8) -> int:
        """Count-proportional ramp: (TC - 1) units, clamped to the spread."""
        units = int(self.betting_count) - 1
        return max(1, min(units, max_units))

    def kelly_bet(self) -> float:
        """Kelly stake for the next round: bankroll x edge / variance,
        scaled by kelly_divisor (2 = half-Kelly). 0 when there is no edge."""
        if self.bankroll <= 0:
            return 0.0
        edge = self.player_edge
        if edge <= 0:
            return 0.0
        return self.bankroll * edge / HAND_VARIANCE / self.kelly_divisor

    def status(self) -> dict:
        s = {
            "system": self.system_name,
            "running_count": round(self.running_count, 1),
            "true_count": round(self.true_count, 2),
            "betting_tc": round(self.betting_count, 2),
            "cards_seen": self.cards_seen,
            "decks_remaining": round(self.decks_remaining, 2),
            "player_edge_pct": round(self.player_edge * 100, 2),
            "enter": self.should_enter,
            "bet_units": self.bet_units(),
        }
        if not self.system.balanced:
            s["key_count"] = self.key_count
            s["pivot"] = self.system.pivot_rc(self.decks)
        if self.system.ace_neutral:
            s["excess_aces"] = round(self.excess_aces, 1)
        if self.bankroll > 0:
            s["kelly_bet"] = round(self.kelly_bet(), 2)
        return s
