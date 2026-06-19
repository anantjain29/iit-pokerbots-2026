"""Experimental strategy using blockers to select passes and bluff spots."""
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
import random
from itertools import combinations
from collections import Counter

RANK_STR   = '23456789TJQKA'
MAX_SCORE  = 135_004_167
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


def blocker_value(card_strs: list[str]) -> float:
    """
    Measure how many 'blocker' properties this hand has.
    Returns a score in [0, 1].
    Blockers:
      - Aces block nut-flush and ace-high straights
      - Kings block king-high straights and nut-straights
      - Holding 3+ suits blocks opponent from having a flush
      - Suited connectors block straight runs
    """
    ranks = [c[0] for c in card_strs]
    suits = [c[1] for c in card_strs]
    sc    = Counter(suits)

    raw  = 0
    raw += ranks.count('A') * 4   # aces are elite blockers
    raw += ranks.count('K') * 2
    raw += ranks.count('Q') * 1
    raw += ranks.count('J') * 0.5

    # Suit diversity -> blocks opponent flushes
    raw += len(sc) * 0.5

    # 2+ cards of same suit -> flush blocker
    for suit_cnt in sc.values():
        if suit_cnt >= 3:
            raw += 3

    # Normalise to [0, 1] assuming max ~20
    return min(raw / 20.0, 1.0)


def has_flush_draw(card_strs: list[str]) -> bool:
    suits = [c[1] for c in card_strs]
    return max(Counter(suits).values()) >= 5


def has_straight_draw(card_strs: list[str]) -> bool:
    """True if hand has at least 4 consecutive-ranked cards."""
    ranks = sorted(set(RANK_STR.index(c[0]) for c in card_strs))
    for i in range(len(ranks) - 3):
        if ranks[i + 3] - ranks[i] <= 4:
            return True
    return False


def find_pass_idx_blocker(card_strs: list[str], n: int) -> list[int]:
    """
    Pass combination that maximises:  0.75 * equity  +  0.25 * blocker_value
    of the kept cards.
    """
    cards  = parse_cards(card_strs)
    num    = len(cards)
    best_combined, best_combo = -1.0, list(range(n))

    for pass_combo in combinations(range(num), n):
        kept_idx  = [i for i in range(num) if i not in pass_combo]
        kept      = [cards[i] for i in kept_idx]
        kept_strs = [card_strs[i] for i in kept_idx]

        eq = score_kept(kept) / MAX_SCORE
        bl = blocker_value(kept_strs)
        combined = 0.75 * eq + 0.25 * bl

        if combined > best_combined:
            best_combined, best_combo = combined, list(pass_combo)

    return sorted(best_combo)


class Player(BaseBot):

    def __init__(self):
        self.hands_played  = 0
        self.bluff_freq    = 0.22   # base bluff frequency, tunable

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        self.hands_played += 1

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        pass

    def get_move(self, game_info: GameInfo, cs: PokerState):
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx_blocker(cs.my_hand, PASS_COUNTS[street]))

        strength = hand_strength(cs.my_hand)
        bl_val   = blocker_value(cs.my_hand)
        f_draw   = has_flush_draw(cs.my_hand)
        s_draw   = has_straight_draw(cs.my_hand)

        # Enhanced bluff probability when holding strong blockers
        bluff_prob = self.bluff_freq * (1.0 + bl_val)
        is_bluff   = random.random() < bluff_prob

        # Semi-bluff draws: raises with draws AND blockers
        is_semi    = (f_draw or s_draw) and bl_val > 0.4

        pot  = cs.pot
        cost = cs.cost_to_call

        if cs.can_act(ActionRaise):
            lo, hi = cs.raise_bounds
            if strength > 0.70:                         # value
                raise_to = min(hi, lo + int((hi - lo) * 0.80))
                return ActionRaise(raise_to)
            if (is_bluff and bl_val > 0.50) or is_semi: # bluff / semi-bluff
                return ActionRaise(lo)
            if strength > 0.52:
                return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        pot_odds = cost / (pot + cost) if (pot + cost) > 0 else 1.0

        # Call wider when blocker equity is high (we "hold" some of opp's outs)
        adjusted_threshold = pot_odds - bl_val * 0.12

        if strength > adjusted_threshold or (is_bluff and bl_val > 0.55):
            return ActionCall()

        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
