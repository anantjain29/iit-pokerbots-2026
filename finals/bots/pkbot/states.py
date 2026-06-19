'''
Encapsulates game and round state information for the player.
'''
from collections import namedtuple
from .actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass

GameInfo = namedtuple('GameInfo', ['bankroll', 'time_bank', 'round_num'])
HandResult = namedtuple('HandResult', ['payoffs', 'parent_state'])

STARTING_STACK = 5000
BIG_BLIND = 20
SMALL_BLIND = 10

STREET_LABELS  = ['TriplePass', 'Betting#1', 'DoublePass', 'Betting#2', 'SinglePass', 'Betting#3']

class GameState(namedtuple('_GameState', ['dealer', 'street', 'wagers', 'chips', 'hands', 'parent_state'])):
    '''Encodes the game tree for one round of poker.'''

    def calculate_result(self):
        '''Compares the players' hands and computes payoffs.'''
        return HandResult([0, 0], self)

    @property
    def legal_actions(self):
        '''Returns the set of actions available to the current player.'''
        if self.street % 2 == 0:
            return {ActionPass}
    
        active_idx = self.dealer % 2
        cost_to_call = self.wagers[1-active_idx] - self.wagers[active_idx]
        
        if cost_to_call == 0:
            # Check or Raise allowed, unless all-in
            cannot_bet = (self.chips[0] == 0 or self.chips[1] == 0)
            return {ActionCheck} if cannot_bet else {ActionCheck, ActionRaise}
        
        # Must Call or Fold (or Raise if possible)
        cannot_raise = (cost_to_call == self.chips[active_idx] or self.chips[1-active_idx] == 0)
        return {ActionFold, ActionCall} if cannot_raise else {ActionFold, ActionCall, ActionRaise}
    
    @property
    def raise_bounds(self):
        '''Returns (min_raise, max_raise) for the active player.'''
        active_idx = self.dealer % 2
        cost = self.wagers[1-active_idx] - self.wagers[active_idx]
        max_bet = min(self.chips[active_idx], self.chips[1-active_idx] + cost)
        min_bet = min(max_bet, cost + max(cost, BIG_BLIND))
        return (self.wagers[active_idx] + min_bet, self.wagers[active_idx] + max_bet)

    def next_street(self):
        '''Moves the game to the next betting round or showdown.'''
        if self.street == 5:
            return self.calculate_result()
        return GameState(1, self.street + 1, [0, 0], self.chips, self.hands, self)

    def apply_action(self, action):
        '''Transitions the state based on the action taken.'''
        active = self.dealer % 2

        match action:
            case ActionFold():
                delta = self.chips[0] - STARTING_STACK if active == 0 else STARTING_STACK - self.chips[1]
                return HandResult([delta, -delta], self)
            
            case ActionCall():
                if self.dealer == 0:  # SB calls BB
                    return GameState(1, 1, [BIG_BLIND] * 2, [STARTING_STACK - BIG_BLIND] * 2, self.hands, self)
                
                # Match the bet
                next_wagers = list(self.wagers)
                next_chips = list(self.chips)
                amt_to_call = next_wagers[1-active] - next_wagers[active]
                next_chips[active] -= amt_to_call
                next_wagers[active] += amt_to_call
                
                state = GameState(self.dealer + 1, self.street, next_wagers, next_chips, self.hands, self)
                return state.next_street()
        
            case ActionCheck():
                if self.dealer > 1:
                    return self.next_street()
                return GameState(self.dealer + 1, self.street, self.wagers, self.chips, self.hands, self)
            
            case ActionRaise(amount):
                next_wagers = list(self.wagers)
                next_chips = list(self.chips)
                added = amount - next_wagers[active]
                next_chips[active] -= added
                next_wagers[active] += added
                return GameState(self.dealer + 1, self.street, next_wagers, next_chips, self.hands, self)

            case ActionPass(indicies):
                raise ValueError("Shouldn't handle this client side;")

            case _:
                raise ValueError(f'Invalid action applied to GameState: {action}')

class PokerState:
    '''A wrapper around GameState to provide cleaner access to game information.'''
    is_terminal: bool
    street: str
    my_hand: list[str]
    my_chips: int
    opp_chips: int
    my_wager: int
    opp_wager: int
    pot: int
    cost_to_call: int
    is_bb: bool
    legal_actions: set
    payoff: int
    raise_bounds: tuple[int, int]

    def __init__(self, state: GameState, active: int):
        self.is_terminal = isinstance(state, HandResult)
        # If terminal, we look at the parent state for the board/hands info
        current_state = state.parent_state if self.is_terminal else state

        self.street = STREET_LABELS[current_state.street]
        self.my_hand = current_state.hands[active]
        self.opp_hand = current_state.hands[1-active]
        
        self.my_chips = current_state.chips[active]
        self.opp_chips = current_state.chips[1-active]
        self.my_wager = current_state.wagers[active]
        self.opp_wager = current_state.wagers[1-active]
        
        self.pot = (STARTING_STACK - self.my_chips) + (STARTING_STACK - self.opp_chips)
        self.cost_to_call = self.opp_wager - self.my_wager
        self.is_bb = active == 1
        
        if self.is_terminal:
            self.legal_actions = set()
            self.payoff = state.payoffs[active]
            self.raise_bounds = (0, 0)

        else:
            self.legal_actions = current_state.legal_actions
            self.payoff = 0
            self.raise_bounds = current_state.raise_bounds

    def can_act(self, action_cls):
        '''Checks if a specific action class is currently legal.'''
        return action_cls in self.legal_actions