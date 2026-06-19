"""Experimental strategy that adapts betting thresholds to opponent behavior."""
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

def find_pass_idx(card_strs, n):
    cards = parse_cards(card_strs)
    num   = len(cards)
    best_score, best_combo = -1, list(range(n))
    for pass_combo in combinations(range(num), n):
        kept  = [cards[i] for i in range(num) if i not in pass_combo]
        score = score_kept(kept)
        if score > best_score:
            best_score, best_combo = score, list(pass_combo)
    return sorted(best_combo)

def hand_strength(card_strs):
    return best_5_of_n(parse_cards(card_strs)) / MAX_SCORE

# Opponent Model

class OpponentModel:
    """
    Tracks opponent tendencies across the entire match.
    All data is accumulated - the model improves over time.
    """

    def __init__(self):
        # Per-action counters (inferred from state observations)
        self.opp_raised_count  = 0   # times we faced a bet/raise
        self.opp_checked_count = 0   # times opp had the lead and checked
        self.hands_seen        = 0

        # Showdown results
        self.showdown_wins_opp  = 0  # opp won at showdown
        self.showdown_total     = 0

        # Recent window (last 50 hands) for adaptation
        self._recent_bets    = []    # 1 = bet, 0 = check, per street observation
        self._window         = 50

    # Online update

    def observe_facing_bet(self):
        """Called when we enter get_move and see cost_to_call > 0."""
        self.opp_raised_count += 1
        self._recent_bets.append(1)
        if len(self._recent_bets) > self._window:
            self._recent_bets.pop(0)

    def observe_no_bet(self):
        """Called when we enter get_move in a betting street and cost_to_call == 0."""
        self.opp_checked_count += 1
        self._recent_bets.append(0)
        if len(self._recent_bets) > self._window:
            self._recent_bets.pop(0)

    def observe_hand_end(self, payoff: int, opp_hand: list):
        """Called at hand end; infer fold / showdown outcome."""
        self.hands_seen += 1
        if opp_hand:   # showdown occurred
            self.showdown_total += 1
            if payoff < 0:          # we lost -> opponent won showdown
                self.showdown_wins_opp += 1

    # Derived metrics

    @property
    def aggression_rate(self) -> float:
        """Fraction of observed betting streets where opp bet/raised."""
        total = self.opp_raised_count + self.opp_checked_count
        if total == 0:
            return 0.30   # prior: slightly passive
        return self.opp_raised_count / total

    @property
    def recent_aggression(self) -> float:
        """Aggression over last 50 observations (adapts faster)."""
        if not self._recent_bets:
            return 0.30
        return sum(self._recent_bets) / len(self._recent_bets)

    @property
    def showdown_win_rate(self) -> float:
        if self.showdown_total < 5:
            return 0.50   # not enough data
        return self.showdown_wins_opp / self.showdown_total

    @property
    def is_aggressive(self) -> bool:
        return self.recent_aggression > 0.42

    @property
    def is_passive(self) -> bool:
        return self.recent_aggression < 0.18

    def call_threshold(self) -> float:
        """
        Required hand strength to call a bet.
        Aggressive opp -> need stronger hand (they're not bluffing much).
        Passive opp    -> can call lighter (when they finally bet it's value).
        """
        if self.is_aggressive:
            return 0.52
        if self.is_passive:
            return 0.30
        return 0.40

    def raise_size_mult(self) -> float:
        """
        Fraction of (max - min) to add to min_raise.
        Passive players -> smaller raise (they'll fold to a pot-sized raise).
        Aggressive players -> bigger raise (exploit their tendency to call).
        """
        if self.is_aggressive:
            return 0.80
        if self.is_passive:
            return 0.50
        return 0.65

    def bluff_frequency(self) -> float:
        if self.is_passive:
            return 0.32   # passive opps fold a lot, good for bluffing
        if self.is_aggressive:
            return 0.10   # aggressive opp calls / raises back
        return 0.20


class Player(BaseBot):

    def __init__(self):
        self.model          = OpponentModel()
        self._prev_opp_wager = 0
        self._in_betting     = False

    def on_hand_start(self, game_info: GameInfo, cs: PokerState) -> None:
        self._prev_opp_wager = cs.opp_wager
        self._in_betting     = False

    def on_hand_end(self, game_info: GameInfo, cs: PokerState) -> None:
        self.model.observe_hand_end(cs.payoff, cs.opp_hand)

    def _update_model(self, cs: PokerState) -> None:
        """Infer opp's last action from wager change."""
        if cs.street not in PASS_COUNTS:
            if cs.cost_to_call > 0:
                self.model.observe_facing_bet()
            else:
                self.model.observe_no_bet()
        self._prev_opp_wager = cs.opp_wager

    def get_move(self, game_info: GameInfo, cs: PokerState):
        self._update_model(cs)
        street = cs.street

        if street in PASS_COUNTS:
            return ActionPass(find_pass_idx(cs.my_hand, PASS_COUNTS[street]))

        strength  = hand_strength(cs.my_hand)
        pot       = cs.pot
        cost      = cs.cost_to_call
        threshold = self.model.call_threshold()

        if cs.can_act(ActionRaise):
            lo, hi   = cs.raise_bounds
            size_f   = self.model.raise_size_mult()
            bluff_ok = (strength < 0.40
                        and self.model.bluff_frequency() > 0.18
                        and cs.cost_to_call == 0)

            if strength > 0.65:
                return ActionRaise(min(hi, lo + int((hi - lo) * size_f)))
            if strength > threshold - 0.05:       # thin value
                return ActionRaise(lo)
            if bluff_ok:
                return ActionRaise(lo)

        if cs.can_act(ActionCheck):
            return ActionCheck()

        # Pot-odds call with model-adjusted threshold
        pot_odds = cost / (pot + cost) if (pot + cost) > 0 else 1.0
        effective = max(pot_odds + 0.05, threshold - 0.05)

        if strength > effective:
            return ActionCall()
        if cs.can_act(ActionFold):
            return ActionFold()
        return ActionCall()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
