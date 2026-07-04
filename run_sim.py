#!/usr/bin/env python3
"""Run EV scenarios. `python run_sim.py` runs them all."""

from bjbot.simulator import SimConfig, SimRules, run_sim

STAKE_RULES = SimRules(
    dealer_hits_soft_17=False,   # Stake screen: "dealer must stand on 17"
    double_after_split=True,
    late_surrender=False,        # Evolution live blackjack has no surrender
    blackjack_pays=1.5,          # "BLACKJACK PAYS 3 TO 2"
)


def show(title, cfg):
    r = run_sim(cfg)
    print(f"\n=== {title} ===")
    print(f"  rules: {'S17' if not cfg.rules.dealer_hits_soft_17 else 'H17'}, "
          f"DAS={cfg.rules.double_after_split}, LS={cfg.rules.late_surrender}, "
          f"BJ pays {cfg.rules.blackjack_pays}:1 | {cfg.decks} decks, "
          f"pen {int(cfg.penetration*100)}%")
    print(f"  spread: ${cfg.min_bet:.0f}-${cfg.max_bet:.0f}, wong in @ TC+{cfg.enter_tc}, "
          f"{'FLAT' if cfg.flat else 'ramped'}, {'wong' if cfg.wong else 'play-all'}")
    print(f"  base house edge (no count): {r['base_house_edge_pct']:+.2f}%")
    print(f"  played {r['play_rate_pct']}% of {r['dealt_rounds']:,} rounds "
          f"(avg bet ${r['avg_bet']})")
    print(f"  per-hand outcomes:  win {r['win_pct']}%  push {r['push_pct']}%  "
          f"loss {r['loss_pct']}%")
    print(f"  edge on money wagered: {r['edge_on_action_pct']:+.3f}%")
    print(f"  EV/hour @ {cfg.rounds_per_hour:.0f} rounds/hr: ${r['ev_per_hour']:+.2f}")
    print(f"  SD/round ${r['sd_per_played_round']} | N0 {r['n0_rounds']} rounds "
          f"| risk of ruin (${cfg.bankroll:,.0f} bankroll): {r['risk_of_ruin_pct']}%")
    return r


if __name__ == "__main__":
    N = 3_000_000

    # 0) Validation: flat-bet basic strategy, no counting -> should ≈ house edge
    show("VALIDATION: flat basic strategy, no counting (expect ≈ house edge)",
         SimConfig(decks=8, penetration=0.5, wong=False, flat=True,
                   rules=STAKE_RULES, rounds=N, min_bet=5, max_bet=5))

    # 1) Stake as observed: 8 decks, 50% pen, $5-$100 wong+ramp
    show("STAKE (8 deck, 50% pen) — $5-$100, wong in @ TC+2",
         SimConfig(decks=8, penetration=0.5, wong=True, min_bet=5, max_bet=100,
                   bet_per_tc=8, enter_tc=2, rules=STAKE_RULES,
                   rounds_per_hour=50, rounds=N))

    # 2) Stake but wider entry / bigger ramp
    show("STAKE (8 deck, 50% pen) — $5-$100, wong in @ TC+3, steeper ramp",
         SimConfig(decks=8, penetration=0.5, wong=True, min_bet=5, max_bet=100,
                   bet_per_tc=15, enter_tc=3, rules=STAKE_RULES,
                   rounds_per_hour=50, rounds=N))

    # 3) Sensitivity to penetration (same spread), 60 / 66 / 75%
    for pen in (0.60, 0.66, 0.75):
        show(f"STAKE rules but {int(pen*100)}% penetration — $5-$100 wong @ TC+2",
             SimConfig(decks=8, penetration=pen, wong=True, min_bet=5, max_bet=100,
                       bet_per_tc=8, enter_tc=2, rules=STAKE_RULES,
                       rounds_per_hour=50, rounds=N))

    # 4) A genuinely good physical game for contrast: 6 deck, 75% pen, faster
    show("CONTRAST: good physical 6-deck 75% pen, $10-$300, 80 rounds/hr",
         SimConfig(decks=6, penetration=0.75, wong=True, min_bet=10, max_bet=300,
                   bet_per_tc=25, enter_tc=1.5, rules=STAKE_RULES,
                   rounds_per_hour=80, bankroll=15000, rounds=N))
