from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

import eval7
from itertools import combinations
from collections import Counter

# Card and game constants.

RANK_STR  = '23456789TJQKA'
SUITS     = 'cdhs'
FULL_DECK = [r + s for r in RANK_STR for s in SUITS]
E7        = {c: eval7.Card(c) for c in FULL_DECK}

MAX_SCORE   = 135_004_167
PASS_COUNTS = {'TriplePass': 3, 'DoublePass': 2, 'SinglePass': 1}

# Hand evaluation helpers.

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


# Retained-card synergy heuristic.

def synergy_score(cards, card_strs):
    if not cards:
        return 0.0
    ranks = [RANK_STR.index(str(c)[0]) for c in cards]
    suits = [str(c)[1] for c in cards]
    rc = Counter(ranks)
    sc = Counter(suits)

    score = 0.0
    for cnt in rc.values():
        if cnt == 2:   score += 1.0
        elif cnt == 3: score += 3.0
        elif cnt == 4: score += 6.0

    max_suit = max(sc.values())
    score += max_suit * 0.4

    ur = sorted(set(ranks))
    for i in range(1, len(ur)):
        gap = ur[i] - ur[i - 1]
        if gap == 1:   score += 0.6
        elif gap == 2: score += 0.2

    return score


# Pass selection.

def find_pass_greedy(card_strs, n):
    """Choose passes greedily when only partial-hand scores are available."""
    cards     = parse_cards(card_strs)
    remaining = list(range(len(cards)))
    passed    = []

    for _ in range(n):
        best_retained = -1.0
        best_drop = remaining[0]

        for idx in remaining:
            trial   = [cards[i] for i in remaining if i != idx]
            trial_s = [card_strs[i] for i in remaining if i != idx]
            syn     = synergy_score(trial, trial_s)
            eq      = score_kept(trial) / MAX_SCORE if len(trial) >= 4 else 0
            combined = syn * 0.5 + eq * 50
            if combined > best_retained:
                best_retained = combined
                best_drop = idx

        passed.append(best_drop)
        remaining.remove(best_drop)

    return sorted(passed)


def find_pass_exhaustive(card_strs, n, known_opp_strs=None):
    """Enumerate passes when every retained hand can be evaluated exactly."""
    cards = parse_cards(card_strs)
    num   = len(cards)

    # Penalize passes that match cards known to be held by the opponent.
    opp_rc = Counter()
    opp_sc = Counter()
    if known_opp_strs:
        for c in known_opp_strs:
            opp_rc[RANK_STR.index(c[0])] += 1
            opp_sc[c[1]] += 1

    best_score = -float('inf')
    best_pass  = list(range(n))

    for combo in combinations(range(num), n):
        keep_idx = [i for i in range(num) if i not in combo]
        kept     = [cards[i] for i in keep_idx]
        kept_s   = [card_strs[i] for i in keep_idx]

        syn      = synergy_score(kept, kept_s)
        eq       = score_kept(kept) / MAX_SCORE if len(kept) >= 4 else 0
        combined = syn * 0.5 + eq * 50

        if known_opp_strs:
            penalty = 0.0
            for i in combo:
                r = RANK_STR.index(card_strs[i][0])
                s = card_strs[i][1]
                rm = opp_rc.get(r, 0)
                if   rm >= 3: penalty += 3.0    # giving quads
                elif rm == 2: penalty += 1.5    # giving trips
                elif rm == 1: penalty += 0.5    # giving pair
                sm = opp_sc.get(s, 0)
                if   sm >= 4: penalty += 2.0    # completing flush
                elif sm == 3: penalty += 0.8    # 4-flush
            combined -= penalty

        if combined > best_score:
            best_score = combined
            best_pass  = list(combo)

    return sorted(best_pass)


# Card tracking and constrained equity.

class CardTracker:
    """Infer opponent cards from passes that have not returned."""

    def __init__(self):
        self.all_seen     = set()
        self.cards_given  = set()
        self.hand_snapshot = None
        self.just_passed  = set()
        self.pending_sync = False

    def reset(self):
        self.all_seen.clear()
        self.cards_given.clear()
        self.hand_snapshot = None
        self.just_passed.clear()
        self.pending_sync = False

    def init_hand(self, hand):
        self.all_seen = set(hand)

    def sync_after_exchange(self, current_hand_set):
        if not self.pending_sync or self.hand_snapshot is None:
            return
        self.all_seen |= current_hand_set

        # A returned card is no longer known to be in the opponent's hand.
        expected_kept = self.hand_snapshot - self.just_passed
        received = current_hand_set - expected_kept
        returned = received & self.cards_given
        self.cards_given -= returned

        self.pending_sync = False
        self.hand_snapshot = None
        self.just_passed.clear()

    def record_pass(self, hand, pass_indices):
        self.hand_snapshot = set(hand)
        self.just_passed = {hand[i] for i in pass_indices}
        self.cards_given |= self.just_passed
        self.pending_sync = True

    def known_opp_cards(self, my_hand):
        """Cards we've seen that opponent currently holds."""
        return list(self.all_seen - set(my_hand))

    def exact_equity(self, hand_strs):
        """Calculate exact equity when at most two opponent cards are unknown."""
        known_opp = self.known_opp_cards(hand_strs)
        n_unknown = 7 - len(known_opp)

        if n_unknown > 2:
            return None

        my_eval = [E7[c] for c in hand_strs]
        my_score = eval7.evaluate(my_eval)
        known_opp_eval = [E7[c] for c in known_opp]

        # Seen cards cannot be part of the remaining hidden state.
        pool = [E7[c] for c in FULL_DECK if c not in self.all_seen]

        if n_unknown == 0:
            opp_s = eval7.evaluate(known_opp_eval)
            return 1.0 if my_score > opp_s else (0.5 if my_score == opp_s else 0.0)

        if n_unknown == 1:
            wins = ties = 0.0
            for card in pool:
                opp_s = eval7.evaluate(known_opp_eval + [card])
                if my_score > opp_s:   wins += 1
                elif my_score == opp_s: ties += 0.5
            total = len(pool)
            return (wins + ties) / total if total > 0 else 0.5

        wins = ties = 0.0
        count = 0
        for c1, c2 in combinations(pool, 2):
            opp_s = eval7.evaluate(known_opp_eval + [c1, c2])
            if my_score > opp_s:   wins += 1
            elif my_score == opp_s: ties += 0.5
            count += 1
        return (wins + ties) / count if count > 0 else 0.5


class Player(BaseBot):

    def __init__(self):
        self.tracker = CardTracker()
        self._trapped_street = None
        self._trap_active    = False
        self.last_street     = None

    def on_hand_start(self, game_info, cs):
        self.tracker.reset()
        self.tracker.init_hand(cs.my_hand)
        self._trapped_street = None
        self._trap_active    = False
        self.last_street     = None

    def on_hand_end(self, game_info, cs):
        pass

    def get_move(self, game_info, cs):
        street = cs.street
        hand_set = set(cs.my_hand)

        # Exchanges can return a card passed on an earlier street.
        if self.tracker.pending_sync and street != self.last_street:
            self.tracker.sync_after_exchange(hand_set)
        self.last_street = street

        # Pass phases.
        if street in PASS_COUNTS:
            n = PASS_COUNTS[street]

            if street == 'TriplePass':
                indices = find_pass_greedy(cs.my_hand, n)
            else:
                known_opp = self.tracker.known_opp_cards(cs.my_hand)
                opp_strs = known_opp if known_opp else None
                indices = find_pass_exhaustive(cs.my_hand, n, opp_strs)

            self.tracker.record_pass(cs.my_hand, indices)
            return ActionPass(indices)

        # Betting phases.
        strength = hand_strength(cs.my_hand)

        # Prefer constrained equity when card tracking makes it feasible.
        tracked = self.tracker.exact_equity(cs.my_hand)

        pot  = cs.pot
        cost = cs.cost_to_call
        is_very_strong = strength > 0.74

        # Override heuristic strength when tracked equity is decisive.
        if tracked is not None and tracked < 0.12 and cost > 0:
            if cs.can_act(ActionFold):
                return ActionFold()
            if cs.can_act(ActionCheck):
                return ActionCheck()

        if tracked is not None and tracked > 0.88:
            if cs.can_act(ActionRaise):
                lo, hi = cs.raise_bounds
                return ActionRaise(min(hi, lo + int((hi - lo) * 0.90)))
            return ActionCall()

        # Defer a strong hand once to create a check-raise opportunity.
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

        # Fall back to a pot-odds call decision.
        if cs.can_act(ActionCheck):
            return ActionCheck()

        pot_odds = cost / (pot + cost) if (pot + cost) > 0 else 1.0

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
