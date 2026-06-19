"""Experimental strategy combining retained-card synergy with check-raise traps."""
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
from itertools import combinations
from collections import Counter

RANK_STR    = '23456789TJQKA'
MAX_SCORE   = 135_004_167
PASS_COUNTS = {'TriplePass': 3, 'DoublePass': 2, 'SinglePass': 1}


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


def synergy_score(cards: list, card_strs: list[str]) -> float:
    """
    Rate how "synergistic" a set of kept cards is.
    Synergy = pairs/trips/quads + flush connections + straight connections.
    High synergy -> keep together.  Low synergy -> candidate for passing.
    """
    if not cards:
        return 0.0
    ranks = [RANK_STR.index(str(c)[0]) for c in cards]
    suits = [str(c)[1] for c in cards]
    rc    = Counter(ranks)
    sc    = Counter(suits)

    score = 0.0
    # Pair/set/quad bonuses
    for cnt in rc.values():
        if cnt == 2: score += 1.0
        elif cnt == 3: score += 3.0
        elif cnt == 4: score += 6.0

    # Flush connections
    max_suit = max(sc.values())
    score += max_suit * 0.4

    # Straight connectivity
    ur = sorted(set(ranks))
    for i in range(1, len(ur)):
        gap = ur[i] - ur[i-1]
        if gap == 1:   score += 0.6
        elif gap == 2: score += 0.2

    return score


def find_pass_idx_trap(card_strs: list[str], n: int) -> list[int]:
    """
    Pass the cards with the lowest synergy contribution.
    1. Compute synergy of full hand.
    2. For each card, compute synergy WITHOUT that card.
    3. The card whose removal LEAST reduces synergy is the best candidate to pass.
    4. Greedily remove n such cards.
    """
    cards     = parse_cards(card_strs)
    remaining = list(range(len(cards)))
    passed    = []

    for _ in range(n):
        best_retained_synergy = -1
        best_drop = remaining[0]

        for idx in remaining:
            trial    = [cards[i] for i in remaining if i != idx]
            trial_s  = [card_strs[i] for i in remaining if i != idx]
            syn      = synergy_score(trial, trial_s)
            # Also weigh raw hand score
            eq       = score_kept(trial) / MAX_SCORE if len(trial) >= 4 else 0
            combined = syn * 0.5 + eq * 50   # balance synergy & equity
            if combined > best_retained_synergy:
                best_retained_synergy = combined
                best_drop = idx

        passed.append(best_drop)
        remaining.remove(best_drop)

    return sorted(passed)


class Player(BaseBot):

    def __init__(self):
        self._trapped_street  = None
        self._trap_active     = False

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        self._trapped_street = None
        self._trap_active    = False

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def get_move(self, game_info: GameInfo, cs: PokerState):
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx_trap(cs.my_hand, PASS_COUNTS[street]))

        strength = hand_strength(cs.my_hand)
        pot      = cs.pot
        cost     = cs.cost_to_call
        is_very_strong = strength > 0.74

        if cs.can_act(ActionRaise):
            lo, hi = cs.raise_bounds

            if is_very_strong:
                if cost == 0:
                    if not self._trap_active and street != self._trapped_street:
                        self._trap_active    = True
                        self._trapped_street = street
                        if cs.can_act(ActionCheck):
                            return ActionCheck()
                    return ActionRaise(min(hi, lo + int((hi - lo) * 0.85)))

                else:
                    self._trap_active    = False
                    self._trapped_street = None
                    return ActionRaise(min(hi, lo + int((hi - lo) * 0.90)))

            elif strength > 0.55:
                return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        pot_odds = cost / (pot + cost) if (pot + cost) > 0 else 1.0

        # Preserve the trap state when raising is unavailable.
        if self._trap_active and cost > 0:
            self._trap_active = False
            if is_very_strong or strength > 0.55:
                return ActionCall()

        if strength > pot_odds + 0.06 or strength > 0.55:
            return ActionCall()

        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
