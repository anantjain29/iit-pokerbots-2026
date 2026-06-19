'''
1.0.0 IIT-POKERBOTS GAME ENGINE - Anaconda Edition
DO NOT REMOVE, RENAME, OR EDIT THIS FILE
'''
from collections import namedtuple
import eval7
import argparse
import os
from queue import Queue
import subprocess
import socket
from threading import Thread
import time
from datetime import datetime
import traceback
import random

from config import *

PLAYER_LOG_SIZE_LIMIT = 524288
GAME_CLOCK = 20.0
CONNECT_TIMEOUT = 10.0

NUM_ROUNDS = 1000
STARTING_STACK = 5000
BIG_BLIND = 20
SMALL_BLIND = 10

# Format Utils ---------------------------------------------------------------------------------------
CCARDS = lambda cards: ','.join(map(str, cards))
PCARDS = lambda cards: '[{}]'.format(' '.join(map(str, cards)))
PVALUE = lambda name, value: ', {} ({})'.format(name, value)
STATUS = lambda players: ''.join([PVALUE(p.name, p.bankroll) for p in players])
STREET_LABELS  = ['TriplePass', 'Betting#1', 'DoublePass', 'Betting#2', 'SinglePass', 'Betting#3']

# Actions --------------------------------------------------------------------------------------------
ActionFold = namedtuple('ActionFold', [])
ActionCall = namedtuple('ActionCall', [])
ActionCheck = namedtuple('ActionCheck', [])
ActionRaise = namedtuple('ActionRaise', ['amount'])
ActionPass = namedtuple('ActionPass', ['indicies'])
VALID_INDICES = set(range(7))


DECODE_ACTION = {
    'R': ActionRaise,
    'C': ActionCall,
    'K': ActionCheck,
    'F': ActionFold,
    'Z': ActionPass
}

# States ---------------------------------------------------------------------------------------------
HandResult = namedtuple('HandResult', ['payoffs', 'parent_state'])

class GameState(
            namedtuple(
                '_GameState',
                ['dealer', 'street', 'swap_indicies', 'wagers', 'chips', 'hands', 'parent_state']
            )
    ):
    '''Represents the state of the table at a specific point in the hand.'''

    def calculate_result(self):
        '''Determines the winner and calculates the chip transfer.'''
        score0 = eval7.evaluate(self.hands[0])
        score1 = eval7.evaluate(self.hands[1])
        if score0 > score1:
            delta = STARTING_STACK - self.chips[1]
        elif score0 < score1:
            delta = self.chips[0] - STARTING_STACK
        else:  # equal split the pot
            delta = (self.chips[0] - self.chips[1]) // 2
        return HandResult([delta, -delta], self)

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

    @property
    def pass_count(self):
        return 3 - self.street // 2

    def next_street(self):
        '''Moves the game to the next betting round or showdown.'''
        if self.street == 5:
            return self.calculate_result()
        elif self.street == 0:
            return GameState(0, 1, [None, None], [SMALL_BLIND, BIG_BLIND], [STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND], self.hands, self)
        return GameState(1, self.street + 1, [None, None], [0, 0], self.chips, self.hands, self)

    def apply_action(self, action):
        '''Transitions the state based on the action taken.'''
        active = self.dealer % 2

        match action:
            case ActionFold():
                delta = self.chips[0] - STARTING_STACK if active == 0 else STARTING_STACK - self.chips[1]
                return HandResult([delta, -delta], self)
            
            case ActionCall():
                if self.dealer == 0:  # SB calls BB
                    return GameState(1, 1, [None, None], [BIG_BLIND] * 2, [STARTING_STACK - BIG_BLIND] * 2, self.hands, self)
                
                # Match the bet
                next_wagers = list(self.wagers)
                next_chips = list(self.chips)
                amt_to_call = next_wagers[1-active] - next_wagers[active]
                next_chips[active] -= amt_to_call
                next_wagers[active] += amt_to_call
                
                state = GameState(self.dealer + 1, self.street, self.swap_indicies, next_wagers, next_chips, self.hands, self)
                return state.next_street()
        
            case ActionCheck():
                if (self.street == 0 and self.dealer > 0) or self.dealer > 1:
                    return self.next_street()
                return GameState(self.dealer + 1, self.street, self.swap_indicies, self.wagers, self.chips, self.hands, self)
            
            case ActionRaise(amount):
                next_wagers = list(self.wagers)
                next_chips = list(self.chips)
                added = amount - next_wagers[active]
                next_chips[active] -= added
                next_wagers[active] += added
                return GameState(self.dealer + 1, self.street, self.swap_indicies, next_wagers, next_chips, self.hands, self)

            case ActionPass(indicies):
                new_swap = list(self.swap_indicies)

                seen = set()
                clean = []
                for i in indicies:
                    if i in VALID_INDICES and i not in seen:
                        seen.add(i)
                        clean.append(i)
                
                if len(clean) < self.pass_count:
                    print(f"[WARNING] Player {active} sent invalid indices {indicies}, patching with random selection")
                    remaining = list(VALID_INDICES - seen)
                    random.shuffle(remaining)
                    clean += remaining[:self.pass_count - len(clean)]
                elif len(clean) > self.pass_count:
                    print(f"[WARNING] Player {active} sent invalid indices {indicies}, patching with random selection")
                    clean = list(range(self.pass_count))
                
                new_swap[active] = clean

                if None not in new_swap:
                    new_hands = []
                    swap_count = self.pass_count

                    for i in range(2):
                        assert len(new_swap[i]) == swap_count, \
                            f'Invalid number of cards swapped for player {i}: expected {swap_count}, got {len(new_swap[i])}'
                        retained = [c for j, c in enumerate(self.hands[i]) if j not in new_swap[i]]
                        swapped_in = [self.hands[1-i][j] for j in new_swap[1-i]]
                        new_hands.append(retained + swapped_in)

                    # Both players have passed — move to next street
                    next_state = GameState(self.dealer + 1, self.street, new_swap, self.wagers, self.chips, new_hands, self)
                    return next_state.next_street()

                else:
                    # Only one player has passed so far
                    return GameState(self.dealer + 1, self.street, new_swap, self.wagers, self.chips, self.hands, self)

            case _:
                raise ValueError(f'Invalid action applied to GameState: {action}')

# BotWrapper --------------------------------------------------------------------------------------
class BotProcess:
    '''Manages the subprocess and socket connection for a single bot.'''

    def __init__(self, name, file_path):
        self.name = name
        self.file_path = file_path
        self.time_bank = GAME_CLOCK
        self.bankroll = 0
        self.proc = None
        self.client_socket = None
        self.socketfile = None
        self.bytes_queue = Queue()
        self.query_times = []
        self.hand_response_times = {}
        self.wins = 0
    
    def run(self):
        '''Runs the pokerbot and establishes the socket connection.'''
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with server_socket:
                server_socket.bind(('', 0))
                server_socket.settimeout(CONNECT_TIMEOUT)
                server_socket.listen()
                port = server_socket.getsockname()[1]

                env = os.environ.copy()
                bots_path = os.path.abspath(BOTS_FOLDER)
                env["PYTHONPATH"] = os.pathsep.join(
                    part for part in (bots_path, env.get("PYTHONPATH")) if part
                )
                proc = subprocess.Popen(
                    [PYTHON_CMD, self.file_path, str(port)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(self.file_path), env=env)
                self.proc = proc
                
                # function for bot listening
                def enqueue_output(out, queue):
                    try:
                        for line in out:
                            queue.put(line)
                    except ValueError:
                        pass
                
                # start a separate bot listening thread which dies with the program
                Thread(target=enqueue_output, args=(proc.stdout, self.bytes_queue), daemon=True).start()
                
                # block until we timeout or the player connects
                client_socket, _ = server_socket.accept()
                client_socket.settimeout(CONNECT_TIMEOUT)
                sock = client_socket.makefile('rw')

                self.client_socket = client_socket
                self.socketfile = sock
                print(self.name, 'connected successfully')
        
        except (TypeError, ValueError):
            print(self.name, 'run command misformatted')
        
        except OSError as e:
            print(self.name, ' timed out or failed to connect.')
            self.bytes_queue.put(traceback.format_exc().encode())
        
        except socket.timeout:
            print('Timed out waiting for', self.name, 'to connect')

    def stop(self):
        '''Closes the socket connection and stops the pokerbot.'''
        
        if self.socketfile is not None:
            try:
                self.socketfile.write('Q\n')
                self.socketfile.close()
            except socket.timeout:
                print('Timed out waiting for', self.name, 'to disconnect')
            except OSError:
                print('Could not close socket connection with', self.name)
        
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except socket.timeout:
                print('Timed out waiting for', self.name, 'to disconnect')
            except OSError:
                print('Could not close client socket with', self.name)
        
        if self.proc is not None:
            try:
                outs, _ = self.proc.communicate(timeout=CONNECT_TIMEOUT)
                self.bytes_queue.put(outs)
            except subprocess.TimeoutExpired:
                print('Timed out waiting for', self.name, 'to quit')
                self.proc.kill()
                outs, _ = self.proc.communicate()
                self.bytes_queue.put(outs)
        
        os.makedirs(GAME_LOG_FOLDER, exist_ok=True)
        with open(os.path.join(GAME_LOG_FOLDER, self.name + '.plog'), 'wb') as log_file:
            bytes_written = 0
            for output in self.bytes_queue.queue:
                try:
                    bytes_written += log_file.write(output)
                    if bytes_written >= PLAYER_LOG_SIZE_LIMIT:
                        break
                except TypeError:
                    pass

    def query(self, state, player_message, game_log, round_num):
        '''
        Requests one action from the pokerbot over the socket connection.
        At the end of the round, we request a CheckAction from the pokerbot.
        '''
        legal_actions = state.legal_actions if isinstance(state, GameState) else {ActionCheck}
        
        if self.socketfile is not None and self.time_bank > 0.:
            clause = ''
            
            try:
                player_message[0] = 'T{:.3f}'.format(self.time_bank)
                message = ' '.join(player_message) + '\n'
                del player_message[1:]  # do not send redundant action history
                
                # Start measureing resp time -----------------------------------------------------------
                start_time = time.perf_counter()
                
                self.socketfile.write(message)
                self.socketfile.flush()
                
                self.client_socket.settimeout(self.time_bank) # Limit and prevent hang
                clause = self.socketfile.readline().strip()
                
                end_time = time.perf_counter()  # End time tracked
                response_time = end_time - start_time
                self.time_bank -= response_time
                self.query_times.append(response_time)
                self.hand_response_times[round_num] = self.hand_response_times.get(round_num, 0) + response_time

                if self.time_bank <= 0.:
                    raise socket.timeout
    
                # Stop & now process query -----------------------------------------------------------

                action = DECODE_ACTION[clause[0]]
                match (clause[0], action in legal_actions):
                    case ('R', True):
                        amount = int(clause[1:])
                        min_raise, max_raise = state.raise_bounds
                        
                        if min_raise <= amount <= max_raise:
                            return action(amount)

                        game_log.append(f'{self.name} illegal raise amount {amount}')

                    case ('Z', True):
                        indices = list(map(int, clause[1:]))

                        if len(indices) != state.pass_count:
                            print(f"[WARNING] Received: {indices}; Expected length: {state.pass_count}, patching by passing first {state.pass_count} cards")
                            game_log.append(f'{self.name} illegal pass: expected {state.pass_count} indices, got {len(indices)}')
                        elif not all(0 <= i < 7 for i in indices):
                            print(f"[WARNING] Received: {indices}; Invalid indices found, patching by passing first {state.pass_count} cards")
                            game_log.append(f'{self.name} illegal pass: indices out of range {indices}')
                        else:
                            return action(indices)

                    case (('C' | 'K' | 'F'), True):
                        return action()
                
                    case _:
                        game_log.append(f"{self.name} attempted illegal {action}")

            except socket.timeout:
                error_message = self.name + ' ran out of time'
                game_log.append(error_message)
                print(error_message)
                self.time_bank = 0.0

            except OSError:
                error_message = self.name + ' disconnected'
                game_log.append(error_message)
                print(error_message)
                self.time_bank = 0.0

            except (IndexError, KeyError, ValueError) as e:
                game_log.append(self.name + ' response misformatted: ' + str(clause))

        # pass frist n cards if they fail to pass anything
        if ActionPass in legal_actions:
            return ActionPass(list(range(state.pass_count)))
        
        return ActionCheck() if ActionCheck in legal_actions else ActionFold()

# PokerMatch -------------------------------------------------------------------------------------------------
class PokerMatch():
    '''Manages logging and the high-level game procedure.'''

    def __init__(self, small_log=False):
        self.small_log = small_log
        self.timestamp = datetime.now()
        self.log = [self.timestamp.strftime('%Y-%m-%d %H:%M:%S ') + BOT_1_NAME + ' vs ' + BOT_2_NAME]
        self.player_messages = [[], []]

    def log_state(self, players, state: GameState):
        '''Incorporates GameState information into the game log and player messages.'''
        if state.street == 0 and state.dealer == 0:
            if not self.small_log:
                self.log.append(f'{players[0].name} posts blind: {SMALL_BLIND}')
                self.log.append(f'{players[1].name} posts blind: {BIG_BLIND}')
                self.log.append(f'{players[0].name} received {PCARDS(state.hands[0])}')
                self.log.append(f'{players[1].name} received {PCARDS(state.hands[1])}')
    
            else:
                self.log.append(f'{players[0].name}: {PCARDS(state.hands[0])}')
                self.log.append(f'{players[1].name}: {PCARDS(state.hands[1])}')

            self.player_messages[0] = ['T0.', 'P0', 'H' + CCARDS(state.hands[0])]
            self.player_messages[1] = ['T0.', 'P1', 'H' + CCARDS(state.hands[1])]

        
        if (state.street > 1 and state.dealer == 1) or (state.street == 1 and state.dealer == 0):
            self.log.append(
                STREET_LABELS[state.street]
                + PVALUE(players[0].name, STARTING_STACK-state.chips[0])
                + PVALUE(players[1].name, STARTING_STACK-state.chips[1])
            )
        
        if (state.street == 1 and state.dealer == 0) or (state.street % 2 == 1 and state.dealer == 1 and state.street != 1):
            self.player_messages[0].append('P0')
            self.player_messages[0].append('N' + CCARDS(state.hands[0]))
            self.player_messages[1].append('P1')
            self.player_messages[1].append('N' + CCARDS(state.hands[1]))

    def log_action(self, name, hand, action, bet_override):
        '''Incorporates action information into the game log and player messages.'''
        match action:
            case ActionFold():
                phrasing = ' folds'
                code = 'F'

            case ActionCall():
                phrasing = ' calls'
                code = 'C'

            case ActionCheck():
                phrasing = ' checks'
                code = 'K'

            case ActionRaise(amount):
                phrasing = (' bets ' if bet_override else ' raises to ') + str(action.amount)
                code = 'R' + str(amount)

            case ActionPass(indicies):
                phrasing = ' passes ' + PCARDS((c for i, c in enumerate(hand) if i in indicies))
                code = 'Z' + ''.join(map(str, indicies))
        
        if self.small_log:
            self.log.append(name + ' ' + code)
        else:
            self.log.append(name + phrasing)

        self.player_messages[0].append(code)
        self.player_messages[1].append(code)

    def log_result(self, players, result):
        '''Incorporates HandResult information into the game log and player messages.'''
        prev = result.parent_state
        if prev.wagers[0] == prev.wagers[1]:
            hand_types = [eval7.handtype(eval7.evaluate(hand)) for hand in prev.hands]

            self.log.append(f'{players[0].name} shows {PCARDS(prev.hands[0])} -> {hand_types[0]}')
            self.log.append(f'{players[1].name} shows {PCARDS(prev.hands[1])} -> {hand_types[1]}')
    
            self.player_messages[0].append('O' + CCARDS(prev.hands[1]))
            self.player_messages[1].append('O' + CCARDS(prev.hands[0]))
        
        if self.small_log:
            self.log.append(f'{players[0].name}: {result.payoffs[0]:+d}')
            self.log.append(f'{players[1].name}: {result.payoffs[1]:+d}')
        
        else:
            self.log.append('{} awarded {}'.format(players[0].name, result.payoffs[0]))
            self.log.append('{} awarded {}'.format(players[1].name, result.payoffs[1]))
        
        self.player_messages[0].append('D' + str(result.payoffs[0]))
        self.player_messages[1].append('D' + str(result.payoffs[1]))

    def play_hand(self, players, round_num):
        '''Runs one round of poker.'''
        deck = eval7.Deck()
        deck.shuffle()
        hands = [deck.deal(7), deck.deal(7)]
        wagers = [SMALL_BLIND, BIG_BLIND]
        chips = [STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND]
        state = GameState(0, 0, [None, None], wagers, chips, hands, None)
        
        while not isinstance(state, HandResult):
            self.log_state(players, state)
            
            active = state.dealer % 2
            player = players[active]
            
            action = player.query(state, self.player_messages[active], self.log, round_num)
            
            bet_override = (state.wagers == [0, 0])
            self.log_action(player.name, state.hands[active], action, bet_override)

            state = state.apply_action(action)
            # reset after query has consumed the message
            # self.player_messages[0] = self.player_messages[0][:1]  # keep only T slot
            # self.player_messages[1] = self.player_messages[1][:1]  # keep only T slot
                    
        self.log_result(players, state)
        for player, player_message, delta in zip(players, self.player_messages, state.payoffs):
            player.query(state, player_message, self.log, round_num)
            player.bankroll += delta
            
            if delta > 0:
                player.wins += 1

    def run(self):
        '''Runs one game of poker.'''
        start_time = time.perf_counter()
        bots_folder_full = os.path.abspath(BOTS_FOLDER)
        players = [
            BotProcess(BOT_1_NAME, os.path.join(bots_folder_full, BOT_1_FILE_NAME)),
            BotProcess(BOT_2_NAME, os.path.join(bots_folder_full, BOT_2_FILE_NAME))
        ]
    
        for player in players:
            player.run()
    
        for round_num in range(1, NUM_ROUNDS + 1):
            self.log.append('')
            self.log.append('Round #' + str(round_num) + STATUS(players))
            self.play_hand(players, round_num)
            players = players[::-1]
    
        self.log.append('')
        self.log.append('Final' + STATUS(players))

        print("\n=== Game Stats ===")
        for bot in players:
            print(f"\nStats for {bot.name}:")
            total_queries = len(bot.query_times)
            avg_query = sum(bot.query_times) / total_queries if total_queries > 0 else 0.0
            max_query = max(bot.query_times) if total_queries > 0 else 0.0
            avg_hand_time = sum(bot.hand_response_times.values()) / NUM_ROUNDS
            win_rate = bot.wins / NUM_ROUNDS
            avg_payoff = bot.bankroll / NUM_ROUNDS
            
            print(f"  Total Bankroll: {bot.bankroll}")
            print(f"------------------------------------------------------------")
            print(f"  Win Rate: {win_rate:.1%}")
            print(f"  Avg Payoff/Hand: {avg_payoff:.2f}")
            print(f"------------------------------------------------------------")
            print(f"  Avg Response Time (Query): {avg_query:.5f}s")
            print(f"  Avg Response Time (Hand): {avg_hand_time:.5f}s")
            print(f"  Max Response Time: {max_query:.5f}s")

        print(f"\nTotal Match Time: {time.perf_counter() - start_time:.3f}s")
        
        for player in players:
            player.stop()

        name = f"{self.timestamp.strftime('%Y%m%d-%H%M%S-%f')}.glog"
        print('Writing game log to', name)
        os.makedirs(GAME_LOG_FOLDER, exist_ok=True)
        with open(os.path.join(GAME_LOG_FOLDER, name), 'w') as log_file:
            log_file.write('\n'.join(self.log))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--small_log', action='store_true', help='Use compressed logging format')
    args = parser.parse_args()
    print('                                                                              ')
    print('  ██╗██╗████████╗    ██████╗  ██████╗ ██╗  ██╗███████╗██████╗ ██████╗  ██████╗ ████████╗███████╗')
    print('  ██║██║╚══██╔══╝    ██╔══██╗██╔═══██╗██║ ██╔╝██╔════╝██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝')
    print('  ██║██║   ██║       ██████╔╝██║   ██║█████╔╝ █████╗  ██████╔╝██████╔╝██║   ██║   ██║   ███████╗')
    print('  ██║██║   ██║       ██╔═══╝ ██║   ██║██╔═██╗ ██╔══╝  ██╔══██╗██╔══██╗██║   ██║   ██║   ╚════██║')
    print('  ██║██║   ██║       ██║     ╚██████╔╝██║  ██╗███████╗██║  ██║██████╔╝╚██████╔╝   ██║   ███████║')
    print('  ╚═╝╚═╝   ╚═╝       ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝   ╚═╝   ╚══════╝')
    print('                                                                              ')
    print('        〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜        ')
    print('       (@)  ░▒▓  A N A C O N D A   E D I T I O N  ~ Finals 2026  ▓▒░  (@)       ')
    print('        〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜        ')
    print()
    print('  /\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\ >@>  ')
    print()
    print('  Initializing Game Engine...')
    PokerMatch(small_log=args.small_log).run()
