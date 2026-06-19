# Finals: Anaconda Hold'em

This directory contains the organizer-supplied finals engine and my submitted
bot for IIT PokerBots 2026.

## Contents

- `bots/final.py`: submitted finals bot
- `bots/experiments/`: earlier strategy variants
- `bots/pkbot/`: organizer-provided bot protocol
- `engine.py`: organizer-provided match engine
- `tournament.py`: parallel round-robin evaluation harness

Anaconda Hold'em deals seven private cards to each player and requires exchanges
of three, two, and one card before successive betting rounds. The submitted bot
optimizes those exchanges, tracks cards it has seen, estimates the opponent's
known holdings, and uses exact equity when the hidden state is sufficiently
constrained.

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r finals/requirements.txt
```

## Run

```bash
cd finals
python3 engine.py
```

`config.py` defaults to self-play between two instances of `bots/final.py`.

Run a single tournament pairing:

```bash
python3 tournament.py --workers 1 --best-of 1 --no-cache
```

Experiment bots can be selected through `config.py` or a tournament
`--bots-json` file using paths such as `experiments/bot_meta.py`.

See the [finals problem statement](../problem-statements/finals-problem-statement.pdf) for the
full competition format.
