"""Run cached round-robin matches in parallel and print a leaderboard."""

import contextlib
import importlib.util
import io
import itertools
import json
import os
import re
import sys
import time
import traceback
import types
from concurrent.futures import ProcessPoolExecutor, as_completed

BOTS = [
    ('FinalA', './final_bot.py'),
    ('FinalB', './final_bot.py'),
]
PROJECT_DIR      = os.path.dirname(os.path.abspath(__file__))
ENGINE_SCRIPT    = os.path.join(PROJECT_DIR, "engine.py")
GAME_LOG_FOLDER  = "./logs"
CACHE_FILE       = os.path.join(PROJECT_DIR, "tournament_cache.json")

DEFAULT_MAX_DRAW_RETRIES  = 3
CACHE_SAVE_INTERVAL       = 50


# Engine loading (once per worker process)

_engine_module = None


def _load_engine() -> object:
    """Import engine.py once using a temporary config module."""
    global _engine_module
    if _engine_module is not None:
        return _engine_module

    dummy = types.ModuleType("config")
    dummy.PYTHON_CMD = sys.executable
    dummy.BOT_1_NAME = "_INIT_"
    dummy.BOT_1_FILE = ""
    dummy.BOT_2_NAME = "_INIT_"
    dummy.BOT_2_FILE = ""
    dummy.GAME_LOG_FOLDER = GAME_LOG_FOLDER

    saved = sys.modules.get("config")
    sys.modules["config"] = dummy
    try:
        spec = importlib.util.spec_from_file_location("_engine_inproc", ENGINE_SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load engine module from {ENGINE_SCRIPT}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _engine_module = mod
    finally:
        if saved is not None:
            sys.modules["config"] = saved
        else:
            sys.modules.pop("config", None)

    return _engine_module


def _parse_bankrolls(output: str, name1: str, name2: str) -> dict[str, int] | None:
    """Parse bankroll totals from engine stdout."""
    bankrolls: dict[str, int] = {}
    current_bot: str | None = None

    for line in output.splitlines():
        match = re.match(r"\s*Stats for (.+):\s*$", line)
        if match:
            current_bot = match.group(1).strip()
            continue

        total = re.match(r"\s*Total Bankroll:\s*([-+]?\d+)\s*$", line)
        if total and current_bot:
            bankrolls[current_bot] = int(total.group(1))
            current_bot = None

    if name1 in bankrolls and name2 in bankrolls:
        return {name1: bankrolls[name1], name2: bankrolls[name2]}
    return None


def _worker_init():
    """Called once when a worker process starts; pre-loads the engine."""
    _load_engine()


def _run_once_inprocess(name1: str, file1: str, name2: str, file2: str) -> dict | None:
    """Run a single game using the pre-loaded engine module."""
    try:
        engine = _load_engine()
        engine.BOT_1_NAME = name1
        engine.BOT_1_FILE = file1
        engine.BOT_2_NAME = name2
        engine.BOT_2_FILE = file2
        engine.GAME_LOG_FOLDER = GAME_LOG_FOLDER
        engine.PYTHON_CMD = sys.executable

        old_cwd = os.getcwd()
        try:
            os.chdir(PROJECT_DIR)
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                engine.PokerMatch(small_log=True).run()
            return _parse_bankrolls(captured.getvalue(), name1, name2)
        finally:
            os.chdir(old_cwd)
    except Exception:
        traceback.print_exc()
        return None


# Cache helpers

def cache_key(name_a: str, name_b: str, match_idx: int) -> str:
    pair = "__".join(sorted([name_a, name_b]))
    return f"{pair}__m{match_idx}"


def load_cache(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path: str, cache: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=2)
    os.replace(tmp, path)   # atomic on POSIX; avoids corrupt cache on crash


def purge_draw_entries(cache: dict) -> int:
    """Remove all cache entries belonging to matches that ended in draws
    so they will be replayed on the next run.  Returns the number of
    match groups purged."""
    from collections import defaultdict
    groups = defaultdict(list)
    for key in list(cache.keys()):
        # key format: name_a__name_b__m{idx}__a{attempt}
        parts = key.rsplit("__a", 1)
        if len(parts) == 2:
            groups[parts[0]].append(key)

    purged = 0
    for prefix, keys in groups.items():
        # Find the last (highest) attempt
        last_key = max(keys, key=lambda k: int(k.rsplit("__a", 1)[1]))
        entry = cache[last_key]
        values = list(entry.values())
        if len(values) == 2 and values[0] == values[1]:
            # Final result was a draw - remove all attempts so it's replayed
            for k in keys:
                del cache[k]
            purged += 1

    return purged


# Match runner (with draw replays + cache)

def _relevant_cache_keys(key_prefix: str, max_draw_retries: int) -> list[str]:
    """Return the set of cache keys a match job might look up."""
    return [f"{key_prefix}__a{a}" for a in range(1, max_draw_retries + 2)]


def _try_resolve_from_cache(
    name1: str, name2: str, key_prefix: str,
    cache: dict, max_draw_retries: int,
) -> tuple[dict, int] | None:
    """Attempt to fully resolve a match from cache alone.
    Returns (cumulative_bankrolls, draws_played) or None if any attempt is missing."""
    cumulative = {name1: 0, name2: 0}
    draws_played = 0
    for attempt in range(1, max_draw_retries + 2):
        attempt_key = f"{key_prefix}__a{attempt}"
        entry = cache.get(attempt_key)
        if entry is None:
            return None  # cache miss - must run in worker
        bank1, bank2 = entry[name1], entry[name2]
        cumulative[name1] += bank1
        cumulative[name2] += bank2
        if bank1 != bank2:
            return cumulative, draws_played
        draws_played += 1
        if attempt > max_draw_retries:
            return cumulative, draws_played
    return cumulative, draws_played


def run_match_job(
    name1: str, file1: str, name2: str, file2: str,
    key_prefix: str, cache: dict, max_draw_retries: int,
) -> tuple[dict | None, int, dict]:
    """
    Run one match (with draw replays).  Checks cache before every attempt.
    Returns (cumulative_bankrolls, draws_played, new_entries).
    `cache` only contains the subset of keys relevant to this match.

    Fully cached matches are resolved by the parent process and never reach
    this worker function.
    """
    cumulative = {name1: 0, name2: 0}
    draws_played = 0
    new_entries: dict = {}

    for attempt in range(1, max_draw_retries + 2):
        attempt_key = f"{key_prefix}__a{attempt}"

        if attempt_key in cache:
            entry = cache[attempt_key]
            bank1, bank2 = entry[name1], entry[name2]
        else:
            result = _run_once_inprocess(name1, file1, name2, file2)
            if result is None:
                return None, draws_played, {}
            bank1, bank2 = result[name1], result[name2]
            new_entries[attempt_key] = {name1: bank1, name2: bank2}

        cumulative[name1] += bank1
        cumulative[name2] += bank2

        if bank1 != bank2:
            return cumulative, draws_played, new_entries

        draws_played += 1
        if attempt > max_draw_retries:
            return cumulative, draws_played, new_entries

    return cumulative, draws_played, new_entries


# Job wrapper (top-level so it's picklable for multiprocessing)

def _job_wrapper(args):
    name_a, file_a, name_b, file_b, key, cache_snapshot, max_draw_retries = args
    return (name_a, name_b), run_match_job(
        name_a, file_a, name_b, file_b, key, cache_snapshot, max_draw_retries
    )


# Main tournament

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Round-robin poker tournament")
    parser.add_argument("--best-of",          type=int, default=1)
    parser.add_argument("--workers",          type=int, default=os.cpu_count())
    parser.add_argument("--max-draw-retries", type=int, default=DEFAULT_MAX_DRAW_RETRIES)
    parser.add_argument("--no-cache",         action="store_true")
    parser.add_argument("--clear-cache",      action="store_true")
    args = parser.parse_args()

    if args.clear_cache:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print(f"Cache cleared: {CACHE_FILE}")
        else:
            print("No cache file found.")
        return

    n         = len(BOTS)
    pairings  = list(itertools.combinations(range(n), 2))
    total_m   = len(pairings) * args.best_of

    print("=" * 70)
    print(f"  POKER TOURNAMENT - {n} bots, {len(pairings)} pairings"
          f" x {args.best_of} = {total_m} matches")
    print(f"  Workers: {args.workers}  |  Max draw retries: {args.max_draw_retries}")
    print(f"  Cache: {'DISABLED' if args.no_cache else CACHE_FILE}")
    print("=" * 70)
    for i, (name, path) in enumerate(BOTS):
        print(f"  [{i+1:2d}] {name:<15}  ({path})")
    print("=" * 70)
    print()

    cache: dict = {} if args.no_cache else load_cache(CACHE_FILE)

    # Purge cached draws so they get replayed
    if not args.no_cache:
        purged = purge_draw_entries(cache)
        if purged:
            print(f"  Purged {purged} draw match(es) from cache - will replay.")
            save_cache(CACHE_FILE, cache)

    stats = {
        name: {"total_bankroll": 0, "match_wins": 0, "match_losses": 0,
               "match_draws": 0, "matches_played": 0, "draw_replays": 0}
        for name, _ in BOTS
    }
    h2h = {}

    def _apply_result(name_a, name_b, result, draw_replays, from_cache):
        """Update stats/h2h from a match result."""
        nonlocal completed, failed, cache_hits, total_draw_replays
        completed += 1
        total_draw_replays += draw_replays
        if from_cache:
            cache_hits += 1
        if result is None:
            failed += 1
            return
        bank_a, bank_b = result[name_a], result[name_b]
        stats[name_a]["total_bankroll"]  += bank_a
        stats[name_b]["total_bankroll"]  += bank_b
        stats[name_a]["matches_played"]  += 1
        stats[name_b]["matches_played"]  += 1
        stats[name_a]["draw_replays"]    += draw_replays
        stats[name_b]["draw_replays"]    += draw_replays
        if bank_a > bank_b:
            stats[name_a]["match_wins"]   += 1
            stats[name_b]["match_losses"] += 1
        elif bank_b > bank_a:
            stats[name_b]["match_wins"]   += 1
            stats[name_a]["match_losses"] += 1
        else:
            stats[name_a]["match_draws"]  += 1
            stats[name_b]["match_draws"]  += 1
        h2h[(name_a, name_b)] = h2h.get((name_a, name_b), 0) + bank_a
        h2h[(name_b, name_a)] = h2h.get((name_b, name_a), 0) + bank_b

    # ---- Phase 1: resolve fully-cached matches in-process (zero IPC) ----
    jobs = []
    start_time = time.time()
    completed = failed = cache_hits = total_draw_replays = 0
    pending_saves = 0
    total_matches_label = total_m
    pre_resolved = 0

    for idx_a, idx_b in pairings:
        name_a, file_a = BOTS[idx_a]
        name_b, file_b = BOTS[idx_b]
        for match_idx in range(args.best_of):
            key = cache_key(name_a, name_b, match_idx)

            # Try to resolve entirely from cache - no pickling, no IPC
            if not args.no_cache:
                cached = _try_resolve_from_cache(
                    name_a, name_b, key, cache, args.max_draw_retries)
                if cached is not None:
                    result, draw_replays = cached
                    _apply_result(name_a, name_b, result, draw_replays, True)
                    pre_resolved += 1
                    continue

            # Only pass the tiny subset of cache keys the worker needs
            relevant_keys = _relevant_cache_keys(key, args.max_draw_retries)
            mini_cache = {k: cache[k] for k in relevant_keys if k in cache}
            jobs.append((name_a, file_a, name_b, file_b, key,
                         mini_cache, args.max_draw_retries))

    remaining = len(jobs)
    if pre_resolved:
        print(f"  {pre_resolved} matches resolved from cache instantly.")
    print(f"  Launching {remaining} matches"
          f" across {args.workers} workers ...\n")

    # ---- Phase 2: run remaining matches in parallel workers ----
    worker_done = 0
    if jobs:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_worker_init,
        ) as pool:
            futures = [pool.submit(_job_wrapper, job) for job in jobs]

            for future in as_completed(futures):
                (name_a, name_b), (result, draw_replays, new_entries) = future.result()
                worker_done += 1

                _apply_result(name_a, name_b, result, draw_replays, False)

                # Merge new cache entries from the worker back into main cache
                if new_entries and not args.no_cache:
                    cache.update(new_entries)
                    pending_saves += 1
                    if pending_saves >= CACHE_SAVE_INTERVAL:
                        save_cache(CACHE_FILE, cache)
                        pending_saves = 0

                if result is None:
                    print(f"[{worker_done}/{remaining}] {name_a} vs {name_b} ... FAILED")
                    continue

                bank_a, bank_b = result[name_a], result[name_b]
                replay_note = (f" (+{draw_replays} draw replay"
                               f"{'s' if draw_replays != 1 else ''})" if draw_replays else "")

                if bank_a > bank_b:
                    winner_tag = f"{name_a} wins"
                elif bank_b > bank_a:
                    winner_tag = f"{name_b} wins"
                else:
                    winner_tag = f"DRAW after {draw_replays} retries (max reached)"

                print(f"[{worker_done}/{remaining}] {name_a} vs {name_b}  =>  "
                      f"{name_a} {bank_a:+d}  |  {name_b} {bank_b:+d}"
                      f"  ({winner_tag}){replay_note}")

    # Final cache flush
    if pending_saves and not args.no_cache:
        save_cache(CACHE_FILE, cache)

    elapsed = time.time() - start_time

    ranking = sorted(stats.items(),
                     key=lambda x: (x[1]["match_wins"], x[1]["total_bankroll"]),
                     reverse=True)

    print()
    print("=" * 100)
    print("  FINAL LEADERBOARD")
    print("=" * 100)
    print(f"  {'Rank':<5} {'Bot':<15} {'W':>4} {'L':>4} {'D':>4} "
          f"{'Played':>7} {'Total Bankroll':>16} {'Avg Bankroll':>14} {'Draw Replays':>14}")
    print("-" * 100)
    for rank, (name, s) in enumerate(ranking, 1):
        played = s["matches_played"]
        avg    = s["total_bankroll"] / played if played else 0
        print(f"  {rank:<5} {name:<15} {s['match_wins']:>4} {s['match_losses']:>4} "
              f"{s['match_draws']:>4} {played:>7} {s['total_bankroll']:>+16d} "
              f"{avg:>+14.1f} {s['draw_replays']:>14}")
    print("=" * 100)

    bot_names = [name for name, _ in BOTS]
    col_w = max(len(n) for n in bot_names) + 2

    print()
    print("  HEAD-TO-HEAD BANKROLL (row vs column)")
    print("  " + " " * col_w + "".join(f"{n:>{col_w}}" for n in bot_names))
    for na in bot_names:
        row = f"  {na:<{col_w}}"
        for nb in bot_names:
            row += f"{'---':>{col_w}}" if na == nb else f"{h2h.get((na, nb), 0):>+{col_w}d}"
        print(row)

    print()
    if failed:
        print(f"  {failed} match(es) FAILED")
    if total_draw_replays:
        print(f"  {total_draw_replays} extra game(s) played to break draws")
    print(f"  Cache: {cache_hits}/{total_matches_label} served from cache  ({CACHE_FILE})")
    print(f"  Tournament completed in {elapsed:.1f}s")
    print(f"  {completed - failed} / {total_matches_label} matches successful")
    print()


if __name__ == "__main__":
    main()
