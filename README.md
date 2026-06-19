# IIT PokerBots 2026

**Runner-up (2nd Place), IIT PokerBots 2026**

Competing against 400+ teams from top IITs, I ranked 2nd in the prelims, 1st in the final hackathon, and 2nd overall.

**[View the DominatorBot presentation](DominatorBot_Prelims_Strategy_Presentation.pptx)** for a detailed walkthrough of how I built and iteratively improved my preliminary-round bot, including its architecture, equity engine, auction optimization, opponent modelling, betting strategies, tournament-based evaluation, and performance analysis.

This repository contains the bots, experiments, and evaluation tooling I used to finish second at IIT PokerBots 2026. The competition used two different poker variants: Sneak Peek Hold'em during the seven-day preliminary round and Anaconda Hold'em in the finals. The finals were conducted as a four-hour, offline hackathon.

The competition organizers supplied the game engines, protocol packages, and problem statements. I developed the submitted bot strategies, experimental bots, tournament workflows, and analysis tooling collected here.

## Competition Stages

| Stage   | Variant            | Submitted bot                                  | Main idea                                                                                         |
| ------- | ------------------ | ---------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Prelims | Sneak Peek Hold'em | [`prelims/final_bot.py`](prelims/final_bot.py)         | Equity estimation, auction pricing, opponent adaptation, and position-aware betting               |
| Finals  | Anaconda Hold'em   | [`finals/bots/final_bot.py`](finals/bots/final_bot.py) | Card-exchange optimization, card tracking, exact equity when possible, and selective trap betting |

## Strategy and Evaluation

The prelim bot uses an O(1) lookup table covering all 1,326 unique starting-hand combinations, followed by adaptive, street-aware Monte Carlo evaluation. When an opponent card is known on the river, it exhaustively enumerates the remaining possibilities for exact equity. Its simulation budget scales with the street and remaining time bank to stay within the competition's strict runtime limit.

The strategy has separate modes for information advantage and disadvantage. After winning the auction, it uses reliable equity for thin value bets and tighter call margins; after losing, it suppresses bluffs, applies greater skepticism to opponent bets, and limits investment without a monster hand. An opponent model recalibrated every 18 hands blends recent and cumulative behavior to adapt its calling, bluffing, and bet sizing.

The finals bot treats each forced card exchange as an optimization problem. It scores retained hand strength, avoids passing cards that improve known opponent holdings, tracks cards seen during exchanges, and switches to exact enumeration when the remaining hidden-card space is small enough.

Both stages include tournament harnesses for repeated head-to-head matches. These were used to compare strategies, expose high-variance behavior, and tune decision thresholds before submission. Earlier finals strategies are retained under [`finals/bots/experiments/`](finals/bots/experiments/) to show that iteration process.

### Tournament-Based Bot Selection

I developed around 120 bot variants based on different strategic ideas, then used `tournament.py` to test them against one another in actual head-to-head games. After each tournament, I studied the leaderboard and matchup results, combined the strongest ideas, and selected for performance, low variance, and limited overfitting. Instead of trusting a single noisy match, the harness runs configurable best-of series and ranks bots by match wins and aggregate bankroll, reducing the effect of poker variance on bot selection. It supports round-robin evaluation, parallel worker processes, draw replays, and a head-to-head leaderboard.

To make large experiments practical, the harness preloads the game engine once per worker and stores match results in a persistent cache. Fully cached matches are resolved immediately, workers receive only the cache entries they need, and atomic periodic writes preserve completed work across repeated runs or interruptions. This made it much faster to compare new strategy variants without rerunning unchanged matchups.

### Prelims Auction Optimization

For the Sneak Peek Hold'em auction, I used a data-driven workflow to determine how much the bot should bid for information. The [`analyze_auction.py`](prelims/analyze_auction.py) tool parses self-play logs, estimates hand equity and the value of seeing an opponent card with Monte Carlo simulation, and uses robust linear regression to predict the eventual pot size. It filters outliers and uses K-means to cluster hands into natural equity tiers. For each tier, it estimates the offensive value of seeing an opponent card and the defensive value of denying that information, then blends this theoretical value with observed opponent bid distributions to produce randomized bid ranges.

I then backtested the generated tiered policy against recorded auctions before putting its parameters into the submitted prelim bot. The final policy scales its bid with expected pot size and current equity, allowing it to pay more when the information is likely to be valuable while avoiding overpaying in weaker spots.

## Repository Layout

```text
.
|-- prelims/                 # Sneak Peek Hold'em engine and submitted bot
|   |-- final_bot.py
|   |-- analyze_auction.py
|   |-- tournament.py
|   `-- pkbot/               # Organizer-supplied bot protocol
|-- finals/                  # Anaconda Hold'em engine and submitted bot
|   |-- bots/
|   |   |-- final_bot.py
|   |   |-- experiments/
|   |   `-- pkbot/           # Organizer-supplied bot protocol
|   `-- tournament.py
|-- problem-statements/      # Competition problem statements
`-- DominatorBot_Prelims_Strategy_Presentation.pptx  # Prelims bot strategy presentation
```

## Setup

Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r prelims/requirements.txt
python3 -m pip install -r finals/requirements.txt
```

Each stage must be run from its own directory because the supplied engines use stage-relative configuration and log paths.

## Run the Bots

Run prelim self-play:

```bash
cd prelims
python3 engine.py
```

Run finals self-play:

```bash
cd finals
python3 engine.py
```

The default configurations run two instances of the submitted bot. Edit the corresponding `config.py` to test another matchup.

## Run Tournaments

From either stage directory:

```bash
python3 tournament.py --workers 1 --best-of 1 --no-cache
```

Increase `--workers` and `--best-of` for broader comparisons. Tournament caches and game logs are generated locally and excluded from Git.

For prelim auction-log analysis:

```bash
cd prelims
python3 analyze_auction.py ./logs --bot FinalA
```

## Documentation

* [Prelims bot guide](prelims/BOT_GUIDE.md)
* [Prelims problem statement](problem-statements/prelims-problem-statement.pdf)
* [Finals problem statement](problem-statements/finals-problem-statement.pdf)
* [Prelims bot strategy presentation](DominatorBot_Prelims_Strategy_Presentation.pptx)

## Attribution

Competition engines, `pkbot` protocol code, examples, and problem statements belong to their respective IIT PokerBots 2026 organizers. Bot strategies and evaluation tooling in this repository are by Anant Jain.
