"""
Usage:
  python3 analyze_auction.py ./logs --bot Notato
  python3 analyze_auction.py game.glog  # auto-detects bot
"""

import re, os, sys, argparse, random
import numpy as np
from collections import defaultdict
from pathlib import Path

try:
    import eval7
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'eval7'. Install dependencies first: pip install -r requirements.txt"
    ) from exc


_RV = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
       'T':10,'J':11,'Q':12,'K':13,'A':14}
_SO = {'c':0,'d':1,'h':2,'s':3}
ALL_CARDS = [f'{r}{s}' for s in 'cdhs' for r in '23456789TJQKA']
E7 = {c: eval7.Card(c) for c in ALL_CARDS}
_MC_CACHE = {}


def mc_equity(hand, board, opp_rev=None, n=5000):
    opp_rev = opp_rev or []
    key = (tuple(sorted(hand)), tuple(sorted(board)), tuple(sorted(opp_rev)), int(n))
    if key in _MC_CACHE:
        return _MC_CACHE[key]

    seen = set(hand + board + opp_rev)
    deck = [E7[c] for c in ALL_CARDS if c not in seen]
    my = [E7[c] for c in hand]; brd = [E7[c] for c in board]
    ok = [E7[c] for c in opp_rev]
    od, bd = 2 - len(ok), 5 - len(brd); total = od + bd
    if total > len(deck) or total <= 0: return 0.50
    w = d = 0
    for _ in range(n):
        drawn = random.sample(deck, total)
        hr = eval7.evaluate(my + brd + drawn[od:])
        vr = eval7.evaluate(ok + drawn[:od] + brd + drawn[od:])
        if hr > vr: w += 1
        elif hr == vr: d += 1
    eq = (w + 0.5*d) / n
    _MC_CACHE[key] = eq
    return eq


# LOG PARSER

_RE_ROUND_SPLIT = re.compile(r'\n?Round\s*#', re.IGNORECASE)
_RE_HEADER      = re.compile(r'[\d\-:\s]*(\w+)\s+vs\s+(\w+)', re.IGNORECASE)
_RE_DEAL        = re.compile(r'(\w+)\s+(?:received|dealt|gets)\s+\[(\w+)[,\s]+(\w+)\]', re.IGNORECASE)
_RE_STREET      = re.compile(r'(Flop|Turn|River)\s+\[.+?\]\s*,?\s*(\w+)\s*\((\d+)\)\s*,?\s*(\w+)\s*\((\d+)\)', re.IGNORECASE)
_RE_FLOP_CARDS  = re.compile(r'Flop\s+\[(\w+)[,\s]+(\w+)[,\s]+(\w+)\]', re.IGNORECASE)
_RE_BID         = re.compile(r'(\w+)\s+bids?\s+(\d+)', re.IGNORECASE)
_RE_AUCTION_WIN = re.compile(r'(\w+)\s+(?:won|wins)\s+(?:the\s+)?auction.*?\[(\w+)\]', re.IGNORECASE)
_RE_TIE         = re.compile(r'\btie[d:]?\b', re.IGNORECASE)
_RE_SHOWDOWN = re.compile(r'\bshows?\s+\[', re.IGNORECASE)
_RE_AWARD       = re.compile(r'(\w+)\s+awarded\s+(-?\d+)', re.IGNORECASE)
_RE_BET_ACTION   = re.compile(r'(\w+)\s+bets?\s+(\d+)', re.IGNORECASE)
_RE_RAISE_ACTION = re.compile(r'(\w+)\s+raises?\s+to\s+(\d+)', re.IGNORECASE)


def _canon_name(name):
    return (name or '').strip().lower()


def parse_single_log(path, our_bot):
    with open(path, errors='replace') as f: text = f.read()

    blocks = _RE_ROUND_SPLIT.split(text)

    m = _RE_HEADER.search(blocks[0])
    if not m: return [], None, None
    B1, B2 = m.group(1), m.group(2)
    b1k, b2k = _canon_name(B1), _canon_name(B2)
    ourk = _canon_name(our_bot)
    if ourk not in (b1k, b2k): return [], B1, B2
    opp = B2 if ourk == b1k else B1
    oppk = _canon_name(opp)

    records = []
    for blk in blocks[1:]:
        lines = blk.strip().split('\n')
        if not lines: continue
        rec = dict(opp=opp, our_hand=[], opp_hand=[], flop=[],
                   preflop_pot=0, our_bid=None, opp_bid=None,
                   auction_winner=None, revealed_card=None,
                   our_payoff=0, round_num=0, is_showdown=False,
                   total_pot=0, log_file=os.path.basename(path))

        hm = re.match(r'(\d+),', lines[0])
        if hm: rec['round_num'] = int(hm.group(1))
        last_wager_sum = 0
        pending_bet = 0
        our_w = 0; opp_w = 0
        first_flop = True

        for line in lines:
            cm = _RE_DEAL.search(line)
            if cm:
                who, cards = cm.group(1), [cm.group(2), cm.group(3)]
                whok = _canon_name(who)
                if whok == ourk: rec['our_hand'] = cards
                elif whok == oppk: rec['opp_hand'] = cards

            sm = _RE_STREET.match(line)
            if sm:
                name2 = sm.group(2)
                w1, w2 = int(sm.group(3)), int(sm.group(5))
                last_wager_sum = w1 + w2
                pending_bet = 0
                if _canon_name(name2) == ourk:
                    our_w, opp_w = w1, w2
                else:
                    our_w, opp_w = w2, w1
                if sm.group(1).lower() == 'flop' and first_flop:
                    rec['preflop_pot'] = w1 + w2
                    if not rec['flop']:
                        fc = _RE_FLOP_CARDS.search(line)
                        if fc: rec['flop'] = [fc.group(1), fc.group(2), fc.group(3)]
                    first_flop = False

            bm = _RE_BID.search(line)
            if bm:
                whok = _canon_name(bm.group(1))
                if whok == ourk: rec['our_bid'] = int(bm.group(2))
                elif whok == oppk: rec['opp_bid'] = int(bm.group(2))

            wm = _RE_AUCTION_WIN.search(line)
            if wm:
                rec['revealed_card'] = wm.group(2)
                rec['auction_winner'] = 'us' if _canon_name(wm.group(1)) == ourk else 'opp'

            # Track post-header bet/raise contribution so we can reconstruct
            # the most recent wager amount from action lines.
            bam = _RE_BET_ACTION.search(line)
            if bam and not _RE_BID.search(line):
                pending_bet = int(bam.group(2))

            ram = _RE_RAISE_ACTION.search(line)
            if ram:
                who = _canon_name(ram.group(1))
                baseline = our_w if who == ourk else opp_w
                pending_bet = int(ram.group(2)) - baseline

            if _RE_TIE.search(line):
                rec['auction_winner'] = 'tie'

            if _RE_SHOWDOWN.search(line):
                rec['is_showdown'] = True

            pm = _RE_AWARD.search(line)
            if pm and _canon_name(pm.group(1)) == ourk:
                rec['our_payoff'] = int(pm.group(2))

        if rec['is_showdown']:
            rec['total_pot'] = last_wager_sum + 2 * pending_bet


        if rec['our_bid'] is not None and rec['opp_bid'] is not None and rec['flop'] and rec['is_showdown']:
            records.append(rec)

    return records, opp, our_bot


def load_all_logs(folder, our_bot=None):
    folder = Path(folder)
    glogs = [folder] if folder.is_file() else sorted(folder.glob('*.glog'))
    if not glogs: print("[!] No .glog files found"); sys.exit(1)
    print(f"[+] Found {len(glogs)} .glog file(s)")

    if not our_bot:
        nc = defaultdict(int)
        for gf in glogs:
            with open(gf, errors='replace') as f:
                h = ''.join(f.readline() for _ in range(5))
            m = _RE_HEADER.search(h)
            if m: nc[m.group(1)] += 1; nc[m.group(2)] += 1
        our_bot = max(nc, key=nc.get)
        print(f"[+] Auto-detected bot: '{our_bot}'")

    all_recs, opps = [], set()
    for gf in glogs:
        recs, opp, found = parse_single_log(gf, our_bot)
        if not found:
            print(f"    skip {gf.name}: '{our_bot}' not found"); continue
        opps.add(opp); all_recs.extend(recs)
        print(f"    {gf.name}: {len(recs)} rounds (vs {opp})")
    print(f"\n[+] Total: {len(all_recs)} rounds vs {len(opps)} opponent(s)")
    return all_recs, our_bot, opps


# FIT exp_pot = m * pot + c FROM DATA
def fit_exp_pot(records):
    """Fit exp_pot from observed total_pot vs preflop_pot."""
    pp_raw = np.array([r['preflop_pot'] for r in records], dtype=float)
    tp_raw = np.array([r['total_pot'] for r in records], dtype=float)

    pp, tp, clean = _clean_regression_points(pp_raw, tp_raw)

    def _data_fallback(pp, tp, reason):
        med_ratio = float(np.median(tp / pp)) if len(pp) else 3
        floor = float(np.percentile(tp, 10)) if len(tp) else 50.0
        print(f"  [!] {reason}; using data fallback: "
              f"exp_pot = {med_ratio:.2f}*pot + {floor:.0f}")
        return med_ratio, floor, float('nan'), clean

    if len(pp) < 10:
        return _data_fallback(pp, tp, "Too few clean rounds for linear fit")

    try:
        m, c = np.polyfit(pp, tp, 1)
    except np.linalg.LinAlgError:
        return _data_fallback(pp, tp, "Linear fit failed after cleaning")

    pred = m * pp + c
    ss_res = np.sum((tp - pred)**2)
    ss_tot = np.sum((tp - tp.mean())**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    if r2 < 0.05:
        return _data_fallback(pp, tp,
                              f"Linear fit poor (R^2={r2:.3f}, c={c:.1f})")

    return float(m), float(c), float(r2), clean


def _clean_regression_points(pp, tp):
    """Keep only stable, realistic points for exp_pot regression."""
    stats = {
        'raw': int(len(pp)),
        'removed_invalid': 0,
        'removed_non_growth': 0,
        'removed_ratio_tail': 0,
        'removed_ratio_mad': 0,
        'removed_residual_mad': 0,
    }

    if len(pp) == 0:
        stats['clean'] = 0
        return pp, tp, stats

    # 1) Basic sanity: finite and positive pots.
    mask = np.isfinite(pp) & np.isfinite(tp) & (pp > 0) & (tp > 0)
    stats['removed_invalid'] = int((~mask).sum())
    pp, tp = pp[mask], tp[mask]

    # 2) Hand-level consistency: final showdown pot should not be below preflop pot.
    if len(pp):
        growth_mask = tp >= pp
        stats['removed_non_growth'] = int((~growth_mask).sum())
        pp, tp = pp[growth_mask], tp[growth_mask]

    if len(pp) >= 20:
        ratios = tp / pp

        # 3) Remove extreme ratio tails that usually come from parse artifacts.
        q_lo, q_hi = np.percentile(ratios, [2, 98])
        tail_mask = (ratios >= q_lo) & (ratios <= q_hi)
        if tail_mask.sum() >= 10:
            stats['removed_ratio_tail'] = int((~tail_mask).sum())
            pp, tp = pp[tail_mask], tp[tail_mask]
            ratios = ratios[tail_mask]

        # 4) Robust MAD filter on ratio space.
        med = np.median(ratios)
        mad = np.median(np.abs(ratios - med))
        if mad > 1e-9:
            z = 0.6745 * (ratios - med) / mad
            mad_mask = np.abs(z) <= 3.5
            if mad_mask.sum() >= 10:
                stats['removed_ratio_mad'] = int((~mad_mask).sum())
                pp, tp = pp[mad_mask], tp[mad_mask]

    if len(pp) >= 20:
        # 5) One robust residual pass after initial linear fit.
        try:
            m0, c0 = np.polyfit(pp, tp, 1)
            resid = tp - (m0 * pp + c0)
            med_r = np.median(resid)
            mad_r = np.median(np.abs(resid - med_r))
            if mad_r > 1e-9:
                zr = 0.6745 * (resid - med_r) / mad_r
                resid_mask = np.abs(zr) <= 3.5
                if resid_mask.sum() >= 10:
                    stats['removed_residual_mad'] = int((~resid_mask).sum())
                    pp, tp = pp[resid_mask], tp[resid_mask]
        except np.linalg.LinAlgError:
            pass

    stats['clean'] = int(len(pp))
    return pp, tp, stats


# DERIVE BID RANGE BOUNDS FROM DATA
def derive_bid_range(data):
    """
    Uses distribution of winning auction costs (second-price paid)
    to set lo/hi as fractions of true_value.
    Falls back to 0.70/1.35 only when insufficient data.
    """
    wins = [d for d in data if d['we_won'] and d['auction_cost'] > 0]
    if len(wins) < 15:
        return 0.70, 1.35

    costs = np.array([d['auction_cost'] for d in wins])  # what i actually paid (opp's bid)
    bids  = np.array([d['our_bid']      for d in wins])   # what i proposed of bidding
    fracs = costs / np.maximum(bids, 1)
    fracs = fracs[(fracs > 0) & (fracs <= 2.0)]

    if len(fracs) < 10:
        return 0.70, 1.35

    lo_frac = float(np.percentile(fracs, 25))
    hi_frac = float(np.percentile(fracs, 90))

    bid_lo_mult = max(0.50, min(lo_frac * 1.1, 0.90))
    bid_hi_mult = max(bid_lo_mult + 0.20, min(hi_frac * 1.15, 1.60))

    print(f"  [bid range] cost/bid P25={lo_frac:.3f} P90={hi_frac:.3f} "
          f"-> multipliers [{bid_lo_mult:.2f}, {bid_hi_mult:.2f}]")
    return round(bid_lo_mult, 3), round(bid_hi_mult, 3)


# COMPUTE FEATURES (equity, info value)
def compute_features(records, n_mc=5000):
    print(f"\n[+] Computing equity ({len(records)} rounds, MC n={n_mc})...")
    data = []
    for i, r in enumerate(records):
        if (i+1) % 200 == 0: print(f"    {i+1}/{len(records)}...", end='\r')
        hand, flop = r['our_hand'], r['flop']
        if len(hand) != 2 or len(flop) != 3: continue
        eq = mc_equity(hand, flop, [], n=n_mc)
        we_won = r['auction_winner'] == 'us'
        opp_won = r['auction_winner'] == 'opp'
        cost = r['opp_bid'] if we_won else (r['our_bid'] if r['auction_winner'] == 'tie' else 0)
        iv = None
        if we_won and r['revealed_card']:
            iv = mc_equity(hand, flop, [r['revealed_card']], n=n_mc) - eq
        data.append(dict(
            opp=r['opp'], eq=eq, info_value=iv,
            our_bid=r['our_bid'], opp_bid=r['opp_bid'],
            preflop_pot=r['preflop_pot'], total_pot=r['total_pot'],
            payoff=r['our_payoff'], we_won=we_won, opp_won=opp_won,
            auction_cost=cost,
        ))
    print(f"\n[+] Done: {len(data)} rounds")
    return data


# ANALYSIS HELPERS
def section(t): print(f"\n{'='*65}\n  {t}\n{'='*65}")

def trimmed_mean(a, pct=5):
    a = np.array(a, float)
    if len(a) < 6: return float(a.mean()) if len(a) else 0.0
    lo, hi = np.percentile(a, pct), np.percentile(a, 100-pct)
    t = a[(a >= lo) & (a <= hi)]
    return float(t.mean()) if len(t) else float(a.mean())


def analyze_exp_pot(records, data):
    section("EXP_POT FIT  (total_pot = m x preflop_pot + c)")
    m, c, r2, clean = fit_exp_pot(records)
    kept = clean['clean']
    raw = max(1, clean['raw'])
    print(f"\n  Data cleaning: kept {kept}/{clean['raw']} rounds ({kept/raw:.1%})")
    if kept < clean['raw']:
        print(f"    removed invalid/nonpositive: {clean['removed_invalid']}")
        print(f"    removed non-growth pots:     {clean['removed_non_growth']}")
        print(f"    removed ratio tails:         {clean['removed_ratio_tail']}")
        print(f"    removed ratio MAD outliers:  {clean['removed_ratio_mad']}")
        print(f"    removed residual outliers:   {clean['removed_residual_mad']}")

    print(f"\n  Fitted:  exp_pot = {m:.2f} x pot + {c:.0f}")
    if np.isnan(r2):
        print("  R^2: n/a (fallback model)")
    else:
        print(f"  R^2: {r2:.3f}")
    for pot in [40, 100, 200, 400]:
        print(f"    pot={pot:>3d}  ->  exp_pot = {m*pot + c:.0f}")

    pp = np.array([d['preflop_pot'] for d in data], float)
    tp = np.array([d['total_pot'] for d in data], float)
    pred = m * pp + c
    valid = pp > 0
    err = np.abs(tp[valid] - pred[valid])
    print(f"\n  Validation (n={valid.sum()}):")
    print(f"    Median |error|: {np.median(err):.0f}   Mean: {err.mean():.0f}")
    return m, c


def analyze_offensive(data, m, c):
    section("OFFENSIVE VALUE (seeing their card)")
    info = [d for d in data if d['info_value'] is not None]
    if len(info) < 10:
        print("  [!] Too few rounds"); return 0.0
    ivs = np.array([d['info_value'] for d in info])
    pots = np.array([d['preflop_pot'] for d in info])
    exp_pots = m * pots + c
    chip_vals = np.abs(ivs) * exp_pots
    print(f"\n  Rounds: {len(info)}   Mean |shift|: {np.abs(ivs).mean():.4f}   "
          f"Chip value: {chip_vals.mean():.1f}   Cost paid: {np.mean([d['auction_cost'] for d in info]):.1f}")
    return float(chip_vals.mean())


def analyze_defensive(data):
    section("DEFENSIVE VALUE (empirical)")
    we_won = [d for d in data if d['we_won']]
    opp_won = [d for d in data if d['opp_won']]
    if len(opp_won) < 3:
        print(f"  [!] Only {len(opp_won)} rounds where opp won auction - cannot estimate")
        return 0.0
    tm_we = trimmed_mean([d['payoff'] for d in we_won])
    tm_opp = trimmed_mean([d['payoff'] for d in opp_won])
    total_delta = tm_we - tm_opp
    print(f"\n  We won auction:   n={len(we_won):4d}  trimmed_mean={tm_we:+.1f}")
    print(f"  Opp won auction:  n={len(opp_won):4d}  trimmed_mean={tm_opp:+.1f}")
    print(f"  Total delta:      {total_delta:+.1f} chips/round (off + def combined)")
    return float(total_delta)





# EQUITY TIER CLUSTERING  (k-means)
def _kmeans_boundaries(eqs, n_tiers, n_iter=50):
    """1-D k-means on equity values. Falls back to quantile split."""
    eqs = np.sort(eqs)
    qs = np.linspace(0, 100, n_tiers + 2)[1:-1]
    centroids = np.percentile(eqs, qs)

    for _ in range(n_iter):
        dists = np.abs(eqs[:, None] - centroids[None, :])
        labels = dists.argmin(axis=1)
        new_centroids = np.array([
            eqs[labels == k].mean() if (labels == k).any() else centroids[k]
            for k in range(n_tiers)
        ])
        if np.allclose(new_centroids, centroids, atol=1e-6):
            break
        centroids = new_centroids

    centroids = np.sort(centroids)
    mids = (centroids[:-1] + centroids[1:]) / 2
    boundaries = np.concatenate([[eqs.min() - 1e-6], mids, [eqs.max() + 1e-6]])
    return boundaries


# FIND TIERS - no shrinkage, pure empirical with global fallback
def find_tiers(data, off_global, def_global, m, c, n_tiers=5):
    """
    Build bid tiers from empirical data.

    Per-tier defensive value uses the raw empirical estimate when both
    we_won and opp_won have >= MIN_SAMPLES rounds; otherwise falls back
    to the global estimate.  No Bayesian shrinkage is applied.
    """
    section("OPTIMAL BID TIERS")

    MIN_SAMPLES = 50   # minimum wins AND losses per tier to trust empirical estimate

    eqs      = np.array([d['eq']           for d in data])
    pots     = np.array([d['preflop_pot']  for d in data])
    opp_bids = np.array([d['opp_bid']      for d in data])
    exp_pots = m * pots + c

    info_data    = [(d['eq'], abs(d['info_value']), d['preflop_pot'])
                    for d in data if d['info_value'] is not None]
    we_won_list  = [d for d in data if d['we_won']]
    opp_won_list = [d for d in data if d['opp_won']]

    boundaries = _kmeans_boundaries(eqs, n_tiers)
    bid_lo_mult, bid_hi_mult = derive_bid_range(data)

    tier_results = []
    print(f"\n  Global offensive: {off_global:.0f}   defensive: {def_global:.0f}")
    print(f"  exp_pot = {m:.2f} x pot + {c:.0f}")
    print(f"  MIN_SAMPLES per tier = {MIN_SAMPLES}  (no shrinkage)")
    print(f"\n  {'T':>2}  {'Eq Range':>18}  {'N':>5}  {'Pot':>5}  "
          f"{'Off':>5}  {'Def':>5}  {'TrueVal':>8}  "
          f"{'BidLo':>6}  {'BidHi':>6}  {'fLo':>6}  {'fHi':>6}")

    for t in range(n_tiers):
        lo, hi = boundaries[t], boundaries[t+1]
        is_last_tier = (t == n_tiers - 1)
        mask = (eqs >= lo) & (eqs < hi)
        if is_last_tier:
            mask = (eqs >= lo) & (eqs <= hi)
        if mask.sum() < 5: continue
        n_t     = int(mask.sum())
        avg_pot = float(pots[mask].mean())
        avg_eq  = float(eqs[mask].mean())
        avg_exp = float(exp_pots[mask].mean())

        def _in_tier(eq):
            if is_last_tier:
                return lo <= eq <= hi
            return lo <= eq < hi

        # --- Offensive value for this tier ---
        ti = [(aiv * (m * pp + c)) for (eq, aiv, pp) in info_data
              if _in_tier(eq)]
        off_base = float(np.mean(ti)) if len(ti) >= 10 else off_global

        # --- Defensive value for this tier - pure empirical, no shrinkage ---
        wm = [d for d in we_won_list  if _in_tier(d['eq'])]
        om = [d for d in opp_won_list if _in_tier(d['eq'])]
        if len(wm) >= MIN_SAMPLES and len(om) >= MIN_SAMPLES:
            emp_delta = (trimmed_mean([d['payoff'] for d in wm]) -
                         trimmed_mean([d['payoff'] for d in om]))
            def_base = emp_delta - off_base
            src = f"empirical (n_w={len(wm)}, n_o={len(om)})"
        else:
            def_base = def_global
            src = f"global fallback (n_w={len(wm)}, n_o={len(om)} < {MIN_SAMPLES})"

        # --- Weights to translate raw values into per-auction impact ---
        # Requested shape: parabolic until eq=2/3, then linear.
        if avg_eq <= (2.0 / 3.0):
            off_mult = 12.0 * avg_eq * (1.0 - avg_eq)
        else:
            off_mult = 4.0 * avg_eq
        def_weight  = float(np.clip(0.70 + 1.20 * avg_eq, 0.70, 1.90))

        off_tier  = off_base  * off_mult
        def_tier  = def_base  * def_weight
        true_val  = off_tier  + def_tier

        # --- Bid range: blend value-based bounds with opponent pressure ---
        tier_opp = opp_bids[mask]
        q60_opp  = float(np.percentile(tier_opp, 60))
        q85_opp  = float(np.percentile(tier_opp, 85))

        bid_lo = max(1, int(true_val * bid_lo_mult))
        bid_hi = int(true_val * bid_hi_mult)

        frac_lo   = bid_lo   / max(1, avg_exp)
        frac_hi   = bid_hi   / max(1, avg_exp)
        q60_frac  = q60_opp  / max(1, avg_exp)
        q85_frac  = q85_opp  / max(1, avg_exp)

        frac_lo = float(np.clip(0.55 * frac_lo + 0.45 * q60_frac, 0.02, 0.95))
        frac_hi = float(np.clip(max(frac_lo + 0.03,
                                    0.45 * frac_hi + 0.55 * q85_frac),
                                frac_lo + 0.03, 1.25))


        print(f"  {t:>2}  [{lo:.3f}, {hi:.3f}]  {n_t:>5}  {avg_pot:>5.0f}  "
              f"{off_tier:>5.0f}  {def_tier:>5.0f}  {true_val:>8.0f}  "
              f"{bid_lo:>6}  {bid_hi:>6}  {frac_lo:>6.3f}  {frac_hi:>6.3f}")
        print(f"       def_src: {src}")

        tier_results.append(dict(
            tier=t, eq_lo=float(lo), eq_hi=float(hi), avg_eq=avg_eq,
            n=n_t, avg_pot=avg_pot, avg_exp_pot=avg_exp,
            offensive=off_tier, defensive=def_tier,
            true_value=true_val, bid_lo=bid_lo, bid_hi=bid_hi,
            frac_lo=frac_lo, frac_hi=frac_hi, def_weight=def_weight,
        ))

    return boundaries, tier_results


# GENERATE CODE
def generate_code(m, c, tier_results):
    section("RECOMMENDED AUCTION CODE  (paste into final_bot.py)")

    sorted_tiers = sorted(tier_results, key=lambda t: t['avg_eq'], reverse=True)

    print(f"""
        # Auction.
        if street == 'auction':
            self.pot_at_auction = pot
            self.chips_before_auction = my_chips
            eq = self._equity(cs, gi)
            exp_pot = {m:.2f} * pot + {c:.0f}
""")

    for i, t in enumerate(sorted_tiers):
        kw = "if" if i == 0 else "elif" if i < len(sorted_tiers) - 1 else "else"
        if i < len(sorted_tiers) - 1:
            print(f"                {kw} eq > {t['eq_lo']:.3f}:")
        else:
            print(f"                {kw}:")
        lo = t['frac_lo']
        hi = t['frac_hi']
        print(f"                    bid = int(exp_pot * random.uniform("
              f"{lo:.3f}, {hi:.3f}))")

    print(f"""
            bid = max(0, min(bid, my_chips))
            self.my_bid = bid
            return ActionBid(bid)
""")


# SUMMARY
def summary(data, opponents):
    section("MATCH SUMMARY")
    n = len(data)
    nw = sum(d['we_won'] for d in data)
    no = sum(d['opp_won'] for d in data)
    print(f"\n  Rounds: {n}   We won: {nw} ({nw/n:.0%})   "
          f"Opp won: {no} ({no/n:.0%})   PnL: {sum(d['payoff'] for d in data):+d}")
    if len(opponents) > 1:
        print(f"\n  {'Opponent':>25}  {'N':>5}  {'PnL/r':>7}  "
              f"{'OppMed':>7}  {'TheyWon%':>9}")
        for opp in sorted(opponents):
            r = [d for d in data if d['opp'] == opp]
            ob = [d['opp_bid'] for d in r]
            print(f"  {opp:>25}  {len(r):>5}  "
                  f"{sum(d['payoff'] for d in r)/len(r):>+7.1f}  "
                  f"{np.median(ob):>7.0f}  "
                  f"{sum(d['opp_won'] for d in r)/len(r):>9.1%}")


# BACKTEST
def backtest(data, m, c, tier_results, opponents):
    """
    Replay every round with the recommended tiered strategy and compare
    auction win rate against what actually happened.
    """
    section("BACKTEST - Win Rate with Recommended Strategy")

    if not tier_results:
        print("  [!] No tiers available; skipping backtest")
        return []

    # Mirror generated policy ordering: highest-equity tier first.
    sorted_tiers = sorted(tier_results, key=lambda t: t['avg_eq'], reverse=True)

    def strategy_bid(d):
        pot     = d['preflop_pot']
        exp_pot = m * pot + c
        eq      = d['eq']
        frac    = None
        for t in sorted_tiers[:-1]:
            if eq > t['eq_lo']:
                frac = random.uniform(t['frac_lo'], t['frac_hi'])
                break

        # Fallback to last tier, matching the generated final "else" branch.
        if frac is None:
            t = sorted_tiers[-1]
            frac = random.uniform(t['frac_lo'], t['frac_hi'])
        return int(exp_pot * frac)

    rows = []
    for d in data:
        tier_bid = strategy_bid(d)
        tier_cmp = (tier_bid > d['opp_bid']) - (tier_bid < d['opp_bid'])
        actual_tie = (not d['we_won']) and (not d['opp_won'])
        rows.append(dict(
            opp          = d['opp'],
            actual_won   = d['we_won'],
            actual_tie   = actual_tie,
            actual_score = 1.0 if d['we_won'] else (0.5 if actual_tie else 0.0),
            tiered_won   = (tier_cmp > 0),
            tiered_tie   = (tier_cmp == 0),
            tiered_score = 1.0 if tier_cmp > 0 else (0.5 if tier_cmp == 0 else 0.0),
            tier_bid     = tier_bid,
            opp_bid      = d['opp_bid'],
        ))

    n         = len(rows)
    act_wins  = sum(r['actual_won'] for r in rows)
    act_ties  = sum(r['actual_tie'] for r in rows)
    act_score = sum(r['actual_score'] for r in rows)
    tier_wins = sum(r['tiered_won'] for r in rows)
    tier_ties = sum(r['tiered_tie'] for r in rows)
    tier_score = sum(r['tiered_score'] for r in rows)

    print(f"\n  {'Strategy':<12}  {'Wins':>6}  {'Ties':>6}  {'Score':>9}  {'Delta vs Actual':>16}")
    print(f"  {'-'*67}")
    print(f"  {'Actual':<12}  {act_wins:>6}  {act_ties:>6}  {act_score/n:>8.1%}  {'(baseline)':>16}")
    print(f"  {'Tiered':<12}  {tier_wins:>6}  {tier_ties:>6}  {tier_score/n:>8.1%}  "
          f"  {(tier_score - act_score)/n:>+12.1%}")

    if len(opponents) >= 1:
        print(f"\n  Per-Opponent Breakdown")
        print(f"\n  {'Opponent':>25}  {'N':>5}  "
              f"{'Actual':>7}  {'Tiered':>7}  {'Delta':>9}")
        print(f"  {'-'*75}")
        for opp in sorted(opponents):
            r = [row for row in rows if row['opp'] == opp]
            if not r: continue
            n_o  = len(r)
            a_wr = sum(x['actual_score'] for x in r) / n_o
            t_wr = sum(x['tiered_score'] for x in r) / n_o
            print(f"  {opp:>25}  {n_o:>5}  "
                  f"{a_wr:>7.1%}  {t_wr:>7.1%}  {(t_wr-a_wr):>+9.1%}")

        print(f"\n  Note: backtest uses simplified parameter-only policy.")
        print(f"  Bid model = sampled_tier_frac x exp_pot.")
    return rows


def main():
    ap = argparse.ArgumentParser(description='Analyze auction value from game logs')
    ap.add_argument('path',    help='Folder with .glog files, or single .glog')
    ap.add_argument('--bot',   default=None,  help='Your bot name')
    ap.add_argument('--mc',    type=int, default=10000, help='MC samples per round')
    ap.add_argument('--tiers', type=int, default=5,    help='Number of equity tiers')
    args = ap.parse_args()

    records, our_bot, opponents = load_all_logs(args.path, args.bot)
    if not records: print("[!] No records."); sys.exit(1)

    data = compute_features(records, n_mc=args.mc)
    if not data: print("[!] No data."); sys.exit(1)

    summary(data, opponents)

    m, c = analyze_exp_pot(records, data)

    off_val   = analyze_offensive(data, m, c)
    def_chips = analyze_defensive(data)

    _, tier_results = find_tiers(data, off_val, def_chips, m, c, args.tiers)

    if tier_results:
        generate_code(m, c, tier_results)

    backtest(data, m, c, tier_results, opponents)

    print("\n[Done]")


if __name__ == '__main__':
    main()
