# Prelims: Sneak Peek Hold'em

This directory contains the organizer-supplied preliminary-round engine and my
submitted bot for IIT PokerBots 2026.

## Contents

- `final.py`: submitted preliminary bot
- `engine.py`: organizer-provided match engine
- `pkbot/`: organizer-provided bot protocol
- `tournament.py`: parallel round-robin evaluation harness
- `analyze_auction.py`: auction-log analysis utility
- `BOT_GUIDE.md`: bot API and game integration guide

The preliminary variant is Sneak Peek Hold'em. Its additional auction reveals
information about an opponent card, so the submitted strategy combines equity,
pot size, opponent bidding, and the value of information.

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r prelims/requirements.txt
```

## Run

```bash
cd prelims
python3 engine.py
```

`config.py` defaults to self-play between two instances of `final.py`.

Run a single tournament pairing:

```bash
python3 tournament.py --workers 1 --best-of 1 --no-cache
```

Analyze generated game logs:

```bash
python3 analyze_auction.py ./logs --bot FinalA
```

See the [bot guide](BOT_GUIDE.md) and
[prelims problem statement](../problem-statements/prelims-problem-statement.pdf) for the
protocol and full rules.
