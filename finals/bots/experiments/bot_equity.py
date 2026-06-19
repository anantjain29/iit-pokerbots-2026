"""Experimental strategy driven by normalized eval7 hand strength."""
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
from itertools import combinations
from collections import Counter

RANK_STR  = '23456789TJQKA'
MAX_SCORE = 135_004_167
PASS_COUNTS = {'TriplePass': 3, 'DoublePass': 2, 'SinglePass': 1}

# Hand evaluation helpers.

def parse_cards(card_strs: list[str]) -> list:
    return [eval7.Card(c) for c in card_strs]


def best_5_of_n(cards: list) -> int:
    """Best 5-card eval7 score from n >= 5 cards."""
    if len(cards) == 5:
        return eval7.evaluate(cards)
    return max(eval7.evaluate(list(combo)) for combo in combinations(cards, 5))


def partial_score_4(cards: list) -> int:
    """
    Heuristic strength for a 4-card partial hand.
    Used only during TriplePass when we keep 4 cards.
    Captures: pairs/trips/quads, flush potential, straight potential, rank sum.
    """
    ranks = sorted([RANK_STR.index(str(c)[0]) for c in cards], reverse=True)
    suits = [str(c)[1] for c in cards]
    rc = Counter(ranks)
    sc = Counter(suits)
    counts = sorted(rc.values(), reverse=True)

    score = sum(r * 5_000 for r in ranks)          # high-card base

    if   counts[0] == 4: score += 80_000_000       # four-of-a-kind draw
    elif counts[0] == 3: score += 25_000_000        # trips
    elif counts[0] == 2 and len(counts) > 1 and counts[1] == 2:
                          score += 15_000_000       # two-pair
    elif counts[0] == 2: score += 5_000_000         # one pair

    if max(sc.values()) == 4: score += 10_000_000   # 4-flush

    ur = sorted(set(ranks))
    if len(ur) >= 3 and ur[-1] - ur[0] <= 4:
        score += 3_000_000                          # straight potential

    return score


def score_kept(cards: list) -> int:
    """Score a kept hand of any size."""
    if len(cards) >= 5:
        return best_5_of_n(cards)
    if len(cards) == 4:
        return partial_score_4(cards)
    return sum(RANK_STR.index(str(c)[0]) for c in cards) * 5_000


def find_pass_idx(card_strs: list[str], n: int) -> list[int]:
    """
    Enumerate all C(7, n) pass combinations.
    Return the n indices whose removal maximises kept-hand score.
    C(7,3)=35 and C(7,2)=21 and C(7,1)=7 - all trivially fast.
    """
    cards = parse_cards(card_strs)
    num   = len(cards)
    best_score, best_combo = -1, list(range(n))

    for pass_combo in combinations(range(num), n):
        kept  = [cards[i] for i in range(num) if i not in pass_combo]
        score = score_kept(kept)
        if score > best_score:
            best_score, best_combo = score, list(pass_combo)

    return sorted(best_combo)


def hand_strength(card_strs: list[str]) -> float:
    """Normalised hand strength in [0, 1]."""
    return best_5_of_n(parse_cards(card_strs)) / MAX_SCORE


class Player(BaseBot):

    def __init__(self):
        pass

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def get_move(self, game_info: GameInfo, cs: PokerState):
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx(cs.my_hand, PASS_COUNTS[street]))

        strength = hand_strength(cs.my_hand)
        pot      = cs.pot
        cost     = cs.cost_to_call

        # Value-bet / raise sizing: scale up with strength
        if cs.can_act(ActionRaise):
            lo, hi = cs.raise_bounds
            if strength > 0.75:                         # premium hand
                raise_to = min(hi, lo + int((hi - lo) * 0.85))
                return ActionRaise(raise_to)
            if strength > 0.55:                         # solid hand
                return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        # Facing a bet - pot-odds call decision
        if pot + cost > 0:
            pot_odds = cost / (pot + cost)
        else:
            pot_odds = 1.0

        if strength > pot_odds + 0.08:
            return ActionCall()

        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
