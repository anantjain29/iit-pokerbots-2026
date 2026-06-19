'''
The infrastructure for interacting with the engine.
'''
import argparse
import socket
from .actions import ActionPass, ActionFold, ActionCall, ActionCheck, ActionRaise
from .states import GameInfo, HandResult, GameState, PokerState
from .states import STARTING_STACK, BIG_BLIND, SMALL_BLIND
from .base import BaseBot


class Runner():
    '''Interacts with the engine.'''

    def __init__(self, pokerbot, socketfile):
        self.pokerbot = pokerbot
        self.socketfile = socketfile

    def receive(self):
        '''Generator for incoming messages from the engine.'''
        while True:
            packet = self.socketfile.readline().strip().split(' ')
            if not packet:
                break
            yield packet

    def send(self, action):
        '''Encodes an action and sends it to the engine.'''
        match action:
            case ActionFold():
                code = 'F'
            case ActionCall():
                code = 'C'
            case ActionCheck():
                code = 'K'
            case ActionRaise(amount):
                code = 'R' + str(amount)
            case ActionPass(indices):
                code = 'Z' + ''.join(map(str, indices))

        self.socketfile.write(code + '\n')
        self.socketfile.flush()

    def run(self):
        '''Reconstructs the game tree based on the action history received from the engine.'''
        game_info = GameInfo(0, 0., 1)
        state: GameState = None
        active = 0
        my_player = 0  # set once at game start, never changes
        round_flag = True

        for packet in self.receive():
            for clause in packet:
                match clause[0]:
                    case 'T':
                        game_info = GameInfo(game_info.bankroll, float(clause[1:]), game_info.round_num)

                    case 'P':
                        if round_flag:
                            active = int(clause[1:])
                        my_player = int(clause[1:])

                    case 'H':
                        hands = [[], []]
                        hands[active] = clause[1:].split(',')
                        wagers = [SMALL_BLIND, BIG_BLIND]
                        chips = [STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND]
                        state = GameState(0, 0, wagers, chips, hands, None)
                        if round_flag:
                            self.pokerbot.on_hand_start(game_info, PokerState(state, active))
                            round_flag = False
                    
                    case 'F':
                        state = state.apply_action(ActionFold())

                    case 'C':
                        state = state.apply_action(ActionCall())

                    case 'K':
                        state = state.apply_action(ActionCheck())

                    case 'R':
                        state = state.apply_action(ActionRaise(int(clause[1:])))
            
                    case 'Z':
                        state = GameState(state.dealer + 1, state.street, state.wagers, state.chips, state.hands, state)

                    case 'N':
                        revised_hands = list(state.hands)
                        revised_hands[my_player] = clause[1:].split(',')
                        next_street_num = state.street + 1
                        if next_street_num == 1:
                            # Mirror engine: dealer=0, carry blind wagers into Betting#1
                            state = GameState(0, 1, [SMALL_BLIND, BIG_BLIND], state.chips, revised_hands, state)
                        else:
                            # Mirror engine: dealer=1, reset wagers for Betting#2 and #3
                            state = GameState(1, next_street_num, [0, 0], state.chips, revised_hands, state)

                    case 'O':
                        # backtrack
                        state = state.parent_state if isinstance(state, HandResult) else state
                        revised_hands = list(state.hands)
                        revised_hands[1-active] = clause[1:].split(',')
            
                        # rebuild history
                        state = GameState(state.dealer, state.street, state.wagers, state.chips,
                                                revised_hands, state.parent_state)
                        state = HandResult([0, 0], state)

                    case 'D':
                        assert isinstance(state, HandResult)
                        delta = int(clause[1:])
                        payoffs = [-delta, -delta]
                        payoffs[active] = delta
                        state = HandResult(payoffs, state.parent_state)
                        game_info = GameInfo(game_info.bankroll + delta, game_info.time_bank, game_info.round_num)
                        self.pokerbot.on_hand_end(game_info, PokerState(state, active))
                        game_info = GameInfo(game_info.bankroll, game_info.time_bank, game_info.round_num + 1)
                        round_flag = True

                    case 'Q':
                        assert isinstance(state, HandResult)
                        return

            if round_flag:  # ack the engine
                self.send(ActionCheck())
            else:
                assert active == state.dealer % 2, f"{active}, {state.dealer}"
                action = self.pokerbot.get_move(game_info, PokerState(state, active))
                self.send(action)

def parse_args():
    '''Parses arguments corresponding to socket connection information.'''
    parser = argparse.ArgumentParser(prog='python3 player.py')
    parser.add_argument('--host', type=str, default='localhost', help='Host to connect to, defaults to localhost')
    parser.add_argument('port', type=int, help='Port on host to connect to')
    return parser.parse_args()

def run_bot(pokerbot, args):
    '''Runs the pokerbot.'''
    assert isinstance(pokerbot, BaseBot)
    try:
        sock = socket.create_connection((args.host, args.port))
    except OSError:
        print('Could not connect to {}:{}'.format(args.host, args.port))
        return
    socketfile = sock.makefile('rw')
    runner = Runner(pokerbot, socketfile)
    runner.run()
    socketfile.close()
    sock.close()