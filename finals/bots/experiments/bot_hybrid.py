"""Experimental weighted strategy combining equity, opponent, and blocker signals."""
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
import random
from itertools import combinations
from collections import Counter

RANK_STR    = '23456789TJQKA'
MAX_SCORE   = 135_004_167
PASS_COUNTS = {'TriplePass': 3, 'DoublePass': 2, 'SinglePass': 1}

# Composite weights
W_EQUITY   = 0.50
W_OPP      = 0.30
W_BLOCKER  = 0.20


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

def hand_strength(card_strs):
    return best_5_of_n(parse_cards(card_strs)) / MAX_SCORE

def blocker_value(card_strs):
    ranks = [c[0] for c in card_strs]
    suits = [c[1] for c in card_strs]
    sc    = Counter(suits)
    raw   = (ranks.count('A') * 4 + ranks.count('K') * 2 +
             ranks.count('Q') + len(sc) * 0.5)
    for cnt in sc.values():
        if cnt >= 3: raw += 3
    return min(raw / 20.0, 1.0)

# Opponent Model (lightweight)

class LightOpponentModel:
    """Minimal opponent model for the hybrid bot."""

    def __init__(self):
        self._bets   = []   # rolling window
        self._window = 60

    def record(self, faced_bet: bool):
        self._bets.append(1 if faced_bet else 0)
        if len(self._bets) > self._window:
            self._bets.pop(0)

    @property
    def aggression(self) -> float:
        if not self._bets: return 0.30
        return sum(self._bets) / len(self._bets)

    def opponent_signal(self, strength: float) -> float:
        """
        Returns [0, 1] signal representing how much opp model SUPPORTS
        aggressive play right now.
        High opponent aggression -> be cautious (lower signal when we're weak).
        Low  opponent aggression -> be aggressive (higher signal).
        """
        agg = self.aggression
        if agg > 0.42:
            # Opp is aggressive: only be aggressive ourselves when strong
            return strength * 0.7
        elif agg < 0.18:
            # Opp is passive: we can bluff and thin-value more
            return min(1.0, strength * 1.3 + 0.10)
        else:
            return strength

# Pass decision

def find_pass_idx_hybrid(card_strs: list[str], n: int) -> list[int]:
    """
    Blend equity and blocker value for pass decision.
    weights: equity 0.80, blocker 0.20
    """
    cards = parse_cards(card_strs)
    num   = len(cards)
    best_combined, best_combo = -1.0, list(range(n))

    for pass_combo in combinations(range(num), n):
        kept_idx  = [i for i in range(num) if i not in pass_combo]
        kept      = [cards[i] for i in kept_idx]
        kept_strs = [card_strs[i] for i in kept_idx]
        eq = score_kept(kept) / MAX_SCORE
        bl = blocker_value(kept_strs)
        combined = 0.80 * eq + 0.20 * bl
        if combined > best_combined:
            best_combined, best_combo = combined, list(pass_combo)

    return sorted(best_combo)


class Player(BaseBot):

    def __init__(self):
        self.opp_model = LightOpponentModel()

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def get_move(self, game_info: GameInfo, cs: PokerState):
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx_hybrid(cs.my_hand, PASS_COUNTS[street]))

        self.opp_model.record(cs.cost_to_call > 0)

        strength = hand_strength(cs.my_hand)
        bl_val   = blocker_value(cs.my_hand)
        opp_sig  = self.opp_model.opponent_signal(strength)

        # Each normalized input keeps the weighted intent in [0, 1].
        composite = (W_EQUITY  * strength +
                     W_OPP     * opp_sig  +
                     W_BLOCKER * bl_val)

        pot  = cs.pot
        cost = cs.cost_to_call

        if cs.can_act(ActionRaise):
            lo, hi = cs.raise_bounds

            if composite > 0.68:
                size_f   = 0.55 + composite * 0.35
                raise_to = min(hi, lo + int((hi - lo) * size_f))
                return ActionRaise(raise_to)

            if composite > 0.48:
                return ActionRaise(lo)

            agg_norm = self.opp_model.aggression
            if composite > 0.30 and agg_norm < 0.25 and cost == 0:
                if random.random() < 0.18:
                    return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        pot_odds = cost / (pot + cost) if (pot + cost) > 0 else 1.0
        if composite > pot_odds + 0.05:
            return ActionCall()

        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
