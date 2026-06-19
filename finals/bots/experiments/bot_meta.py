"""Experimental adaptive strategy combining equity, blockers, SPR, and opponent data."""
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
import random
from itertools import combinations
from collections import Counter, deque

RANK_STR    = '23456789TJQKA'
MAX_SCORE   = 135_004_167
PASS_COUNTS = {'TriplePass': 3, 'DoublePass': 2, 'SinglePass': 1}

# Street aggression multipliers (later streets = more money in pot = raise bigger)
STREET_AGG = {'Betting#1': 0.70, 'Betting#2': 0.80, 'Betting#3': 0.90}

# Composite weights
W_EQ   = 0.45
W_OPP  = 0.25
W_BL   = 0.15
W_SPR  = 0.15

# Core Utilities

def parse_cards(card_strs):
    return [eval7.Card(c) for c in card_strs]

def best_5_of_n(cards):
    if len(cards) == 5:
        return eval7.evaluate(cards)
    return max(eval7.evaluate(list(c)) for c in combinations(cards, 5))

def partial_score_4(cards):
    ranks  = sorted([RANK_STR.index(str(c)[0]) for c in cards], reverse=True)
    suits  = [str(c)[1] for c in cards]
    rc, sc = Counter(ranks), Counter(suits)
    counts = sorted(rc.values(), reverse=True)
    score  = sum(r * 5_000 for r in ranks)
    if   counts[0] == 4: score += 80_000_000
    elif counts[0] == 3: score += 25_000_000
    elif counts[0] == 2 and len(counts) > 1 and counts[1] == 2: score += 15_000_000
    elif counts[0] == 2: score += 5_000_000
    if max(sc.values()) == 4: score += 10_000_000
    return score

def score_kept(cards):
    if len(cards) >= 5: return best_5_of_n(cards)
    if len(cards) == 4: return partial_score_4(cards)
    return sum(RANK_STR.index(str(c)[0]) for c in cards) * 5_000

def hand_strength(card_strs) -> float:
    return best_5_of_n(parse_cards(card_strs)) / MAX_SCORE

def blocker_value(card_strs) -> float:
    ranks = [c[0] for c in card_strs]
    suits = [c[1] for c in card_strs]
    sc    = Counter(suits)
    raw   = (ranks.count('A') * 4 + ranks.count('K') * 2.5 +
             ranks.count('Q') * 1.2 + len(sc) * 0.6)
    for cnt in sc.values():
        if cnt >= 3: raw += 2.5
        if cnt >= 4: raw += 3.0
    return min(raw / 22.0, 1.0)

def has_flush_draw(card_strs) -> bool:
    return max(Counter(c[1] for c in card_strs).values()) >= 5

def has_straight_draw(card_strs) -> bool:
    ranks = sorted(set(RANK_STR.index(c[0]) for c in card_strs))
    for i in range(len(ranks) - 3):
        if ranks[i + 3] - ranks[i] <= 4:
            return True
    return False

# Pass Optimisation

def find_pass_idx_meta(card_strs: list[str], n: int) -> list[int]:
    """
    Enumerate all C(7,n) combos; score each kept set:
        kept_score = 0.78 * equity + 0.22 * blocker
    Returns n indices to pass that maximise kept_score.
    """
    cards = parse_cards(card_strs)
    num   = len(cards)
    best, best_combo = -1.0, list(range(n))

    for pass_combo in combinations(range(num), n):
        kept_idx  = [i for i in range(num) if i not in pass_combo]
        kept      = [cards[i] for i in kept_idx]
        kept_strs = [card_strs[i] for i in kept_idx]
        eq = score_kept(kept) / MAX_SCORE
        bl = blocker_value(kept_strs)
        combined = 0.78 * eq + 0.22 * bl
        if combined > best:
            best, best_combo = combined, list(pass_combo)

    return sorted(best_combo)

# Full Opponent Model

class FullOpponentModel:
    """
    Rich opponent model with per-street aggression tracking,
    showdown win-rate, and recent-window fast adaptation.
    """

    def __init__(self):
        # Global counters
        self.total_bets    = 0
        self.total_checks  = 0
        self.total_hands   = 0
        self.showdown_wins = 0   # opp wins
        self.showdowns     = 0

        # Per-street aggression
        self.street_bets   = {'Betting#1': 0, 'Betting#2': 0, 'Betting#3': 0}
        self.street_checks = {'Betting#1': 0, 'Betting#2': 0, 'Betting#3': 0}

        # Fast adaptation: rolling 40-hand window
        self._recent = deque(maxlen=40)


    def observe(self, street: str, faced_bet: bool):
        if street in self.street_bets:
            if faced_bet:
                self.street_bets[street]   += 1
                self.total_bets            += 1
                self._recent.append(1)
            else:
                self.street_checks[street] += 1
                self.total_checks          += 1
                self._recent.append(0)

    def observe_hand_end(self, payoff: int, opp_hand: list):
        self.total_hands += 1
        if opp_hand:
            self.showdowns += 1
            if payoff < 0:
                self.showdown_wins += 1


    @property
    def global_aggression(self) -> float:
        total = self.total_bets + self.total_checks
        return self.total_bets / total if total > 0 else 0.28

    @property
    def recent_aggression(self) -> float:
        if not self._recent: return 0.28
        return sum(self._recent) / len(self._recent)

    def street_aggression(self, street: str) -> float:
        b = self.street_bets.get(street, 0)
        c = self.street_checks.get(street, 0)
        return b / (b + c) if (b + c) > 0 else self.global_aggression

    @property
    def showdown_win_rate(self) -> float:
        return self.showdown_wins / self.showdowns if self.showdowns >= 10 else 0.50

    @property
    def is_loose_passive(self) -> bool:
        return self.recent_aggression < 0.18

    @property
    def is_tight_aggressive(self) -> bool:
        return self.recent_aggression > 0.42 and self.showdown_win_rate > 0.50

    @property
    def is_bluff_heavy(self) -> bool:
        return self.recent_aggression > 0.42 and self.showdown_win_rate < 0.40

    def call_threshold(self, street: str) -> float:
        """Required strength to call on this street."""
        base = 0.40
        s_agg = self.street_aggression(street)
        if s_agg > 0.45:
            base += 0.10    # vs aggressive: need stronger hand
        elif s_agg < 0.18:
            base -= 0.08    # vs passive: call lighter
        if self.is_bluff_heavy:
            base -= 0.08    # catching bluffs is profitable
        return max(0.20, min(0.65, base))

    def raise_mult(self, street: str) -> float:
        """Fraction of (hi-lo) to add to lo for raise sizing."""
        base = STREET_AGG.get(street, 0.70)
        if self.is_loose_passive:
            base *= 0.75    # small bets get calls from passive players
        if self.is_tight_aggressive:
            base *= 1.10    # size up vs TAGs who might re-raise
        return min(base, 0.95)

    def bluff_frequency(self) -> float:
        if self.is_loose_passive:   return 0.28
        if self.is_tight_aggressive: return 0.08
        if self.is_bluff_heavy:     return 0.12
        return 0.18

# SPR Calculator

def compute_spr(cs: PokerState) -> float:
    """Stack-to-pot ratio for the effective stack."""
    eff_stack = min(cs.my_chips, cs.opp_chips)
    pot       = cs.pot if cs.pot > 0 else 1
    return eff_stack / pot

def spr_signal(spr: float, strength: float) -> float:
    """
    SPR-adjusted commitment signal [0, 1].
    Low SPR (< 3)   -> commit almost any decent hand (strength > 0.35)
    Med SPR (3-10)  -> standard ranges
    High SPR (> 10) -> only commit with strong hands
    """
    if spr < 2.5:
        return 1.0 if strength > 0.32 else 0.35
    elif spr < 6:
        return 1.0 if strength > 0.50 else 0.50 * (strength / 0.50)
    elif spr < 12:
        return strength
    else:
        # Deep stack: penalise medium-strength hands
        return strength * 0.80 if strength < 0.65 else strength

# Dynamic Raise Sizing

def compute_raise(lo: int, hi: int, strength: float,
                  street: str, spr: float, opp: FullOpponentModel) -> int:
    """
    Compute raise amount considering strength, SPR, opp model, street.
    """
    base_mult = opp.raise_mult(street)

    # Adjust for SPR: with low SPR, go bigger (all-in pressure)
    if spr < 3:
        spr_factor = 1.0
    elif spr < 8:
        spr_factor = 0.80
    else:
        spr_factor = 0.65

    # Adjust for hand strength
    str_factor = 0.50 + strength * 0.50   # [0.50, 1.00]

    mult = base_mult * spr_factor * str_factor
    mult = max(0.30, min(mult, 0.98))

    return min(hi, lo + int((hi - lo) * mult))


class Player(BaseBot):

    def __init__(self):
        self.opp     = FullOpponentModel()
        self._trap_street  = None
        self._trap_set     = False

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        self._trap_street = None
        self._trap_set    = False

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        self.opp.observe_hand_end(cs.payoff, cs.opp_hand)

    def get_move(self, game_info: GameInfo, cs: PokerState):
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx_meta(cs.my_hand, PASS_COUNTS[street]))

        self.opp.observe(street, cs.cost_to_call > 0)

        strength  = hand_strength(cs.my_hand)
        bl_val    = blocker_value(cs.my_hand)
        spr       = compute_spr(cs)
        spr_sig   = spr_signal(spr, strength)

        opp_adj   = self.opp.recent_aggression
        if opp_adj > 0.42:
            opp_signal = strength * 0.75      # tighten vs aggressive
        elif opp_adj < 0.18:
            opp_signal = min(1.0, strength * 1.20 + 0.08)  # loosen vs passive
        else:
            opp_signal = strength

        composite = (W_EQ  * strength  +
                     W_OPP * opp_signal +
                     W_BL  * bl_val    +
                     W_SPR * spr_sig)

        cost = cs.cost_to_call
        pot  = cs.pot

        if cs.can_act(ActionRaise):
            lo, hi    = cs.raise_bounds
            call_thr  = self.opp.call_threshold(street)
            bluff_fr  = self.opp.bluff_frequency()

            if strength > 0.76 and cost == 0 and not self._trap_set:
                if cs.can_act(ActionCheck):
                    self._trap_set    = True
                    self._trap_street = street
                    return ActionCheck()

            if self._trap_set and cost > 0 and street == self._trap_street:
                self._trap_set = False
                amt = min(hi, int(lo + (hi - lo) * 0.92))
                return ActionRaise(amt)

            if composite > call_thr + 0.12:
                return ActionRaise(compute_raise(lo, hi, strength, street, spr, self.opp))

            # Passive opponents and strong draws justify thinner raises.
            draw = has_flush_draw(cs.my_hand) or has_straight_draw(cs.my_hand)
            if (composite > call_thr and self.opp.is_loose_passive) or \
               (draw and bl_val > 0.35 and cost == 0):
                return ActionRaise(lo)

            if (composite < 0.30 and cost == 0 and
                    self.opp.is_loose_passive and
                    random.random() < bluff_fr):
                return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        pot_odds   = cost / (pot + cost) if (pot + cost) > 0 else 1.0
        call_thr   = self.opp.call_threshold(street)

        # Low SPR reduces the equity required to commit the remaining stack.
        eff_thr = max(pot_odds + 0.04, call_thr - 0.05)
        if spr < 3:
            eff_thr = max(0.25, eff_thr - 0.10)   # low SPR: commit wider

        if composite > eff_thr:
            if strength > 0.72 and cs.can_act(ActionRaise):
                lo, hi = cs.raise_bounds
                return ActionRaise(compute_raise(lo, hi, strength, street, spr, self.opp))
            return ActionCall()

        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
