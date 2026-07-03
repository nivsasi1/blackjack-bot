"""Hi-Lo card counting: running count, true count, edge estimate, entry signal."""

from dataclasses import dataclass, field

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]

# Hi-Lo tag values. T/J/Q/K/A are -1, 2-6 are +1, 7-9 are 0.
HI_LO = {
    "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0,
    "T": -1, "J": -1, "Q": -1, "K": -1, "A": -1,
}


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


@dataclass
class CardCounter:
    decks: int = 8
    # Fraction of the shoe dealt before the cut card (used only for reporting).
    penetration: float = 0.5
    # Player edge gained per true-count point, and the off-the-top house edge.
    # ~0.5%/TC is the standard Hi-Lo approximation for shoe games.
    edge_per_tc: float = 0.005
    base_house_edge: float = 0.005
    # Wong-in threshold: flag entry when true count reaches this.
    enter_tc: float = 2.0

    running_count: int = 0
    cards_seen: int = 0
    history: list = field(default_factory=list)

    def see(self, rank: str) -> None:
        rank = normalize_rank(rank)
        self.running_count += HI_LO[rank]
        self.cards_seen += 1
        self.history.append(rank)

    def undo(self) -> str | None:
        """Remove the most recently counted card (misdetection correction)."""
        if not self.history:
            return None
        rank = self.history.pop()
        self.running_count -= HI_LO[rank]
        self.cards_seen -= 1
        return rank

    def new_shoe(self) -> None:
        self.running_count = 0
        self.cards_seen = 0
        self.history.clear()

    @property
    def decks_remaining(self) -> float:
        remaining = self.decks - self.cards_seen / 52.0
        return max(remaining, 0.25)  # avoid divide-by-zero blowups at the end

    @property
    def true_count(self) -> float:
        return self.running_count / self.decks_remaining

    @property
    def player_edge(self) -> float:
        """Approximate player edge for the next round (negative = house edge)."""
        return self.true_count * self.edge_per_tc - self.base_house_edge

    @property
    def should_enter(self) -> bool:
        return self.true_count >= self.enter_tc

    def bet_units(self, max_units: int = 8) -> int:
        """Simple count-proportional bet ramp: (TC - 1) units, clamped."""
        units = int(self.true_count) - 1
        return max(1, min(units, max_units))

    def status(self) -> dict:
        tc = self.true_count
        return {
            "running_count": self.running_count,
            "true_count": round(tc, 2),
            "cards_seen": self.cards_seen,
            "decks_remaining": round(self.decks_remaining, 2),
            "player_edge_pct": round(self.player_edge * 100, 2),
            "enter": self.should_enter,
            "bet_units": self.bet_units(),
        }
