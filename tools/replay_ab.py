"""Replay a real sysmon trace in the Python engine: fit a scenario, then A/B the TLC fixes.

Python counterpart of the playground's "Real trace replay" + "Recreate & fix (A/B)" cards.

Usage:
    python tools/replay_ab.py <trace.sysmon | trace.replay.json> [--seeds 20] [--csv run.csv]

Steps: parse (tools/sysmon_to_replay.py layout) -> per-rate success of the real A-MPDUs ->
fit effective SNR at <= main BW (RSSI unused: TLC is SR-driven) + obss<bw> for wider BWs ->
run ReferenceTLC(fw=True) baseline and each fix over N Monte-Carlo seeds (mc_ppdu=True) ->
print the same KPIs as the playground (avg Mbps, drop time, time above main BW, wider-BW commits,
blocked search cycles) next to the real trace.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tlcsim import run_sim, ReferenceTLC, TLCConfig, Channel, Seg, Rate, expected_tpt, all_rates  # noqa: E402
from tlcsim.per_model import phy_per, has_rate, per  # noqa: E402

BANDWIDTHS = [20, 40, 80, 160, 320]
VARIANTS = [
    ("Current FW (baseline)", dict(fw=True)),
    ("+ FIX 1 confirm wider BW", dict(fw=True, wide_confirm=True)),
    ("+ FIX 2 escape MCS-0 floor", dict(fw=True, floor_escape=True)),
    ("+ FIX 3 wider-BW backoff", dict(fw=True, wide_backoff=True)),
    ("+ FIX 7 CTS guard", dict(fw=True, cts_guard=True)),
    ("All simulated fixes", dict(fw=True, wide_confirm=True, floor_escape=True, wide_backoff=True, cts_guard=True)),
]


def load(path):
    if path.lower().endswith('.json'):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    from sysmon_to_replay import convert
    return convert(path)


def median(a):
    b = sorted(a)
    if not b:
        return 0.0
    m = len(b) // 2
    return b[m] if len(b) % 2 else (b[m - 1] + b[m]) / 2


def build_trace(R):
    """Same derivation as the playground's buildTrace(): 100 ms tpt bins, per-rate SR, PR timeline, SCs."""
    q = {}
    for x in R['tx']:
        k = x[10] if len(x) > 10 and x[10] is not None else 1
        q[k] = q.get(k, 0) + 1
    queue = max(q, key=q.get) if q else 1
    tx = [x for x in R['tx'] if (x[10] if len(x) > 10 and x[10] is not None else 1) == queue]
    ts = [a[i][0] for a in (tx, R['lq'], R['stats']) if a for i in (0, -1)]
    t0, dur = min(ts), max(ts) - min(ts)
    outs, last_ok, k, rs = [], {}, 0, R['rs']
    for j, x in enumerate(tx):
        n, tn, rk = x[6] or 0, tx[j + 1][0] if j + 1 < len(tx) else float('inf'), tuple(x[1:5])
        while k < len(rs) and rs[k][0] < x[0]:
            k += 1
        if not n:
            continue
        if k < len(rs) and rs[k][0] < tn:   # TX_RATE_SCALE: success flag, else txed_vs_acked = failed MPDUs
            r = rs[k]; k += 1
            fail = 0 if r[2] else min(r[3] or 0, n)
            outs.append((x[0] - t0, x, n, n - fail, True)); last_ok[rk] = (n - fail) / n
        else:
            outs.append((x[0] - t0, x, n, n * last_ok.get(rk, 1.0), False))
    nb = max(1, int(-(-dur // 100)))
    bins = [0.0] * nb
    for t, x, n, ok, _ in outs:
        bins[min(nb - 1, int(t // 100))] += (x[7] or 0) * ok / n * 8 / 1e5
    rates = {}
    for t, x, n, ok, rep in outs:
        if rep and x[9]:   # first transmissions only: retries are biased by the failure that caused them
            e = rates.setdefault((x[3], x[2], x[1], x[4]), [0, 0])
            e[0] += n; e[1] += ok
    pr = [(l[0] - t0, l[1]) for l in R['lq'] if l[1]]
    bw_ms = {}
    for i, (t, r) in enumerate(pr):
        bw_ms[r['bw']] = bw_ms.get(r['bw'], 0) + ((pr[i + 1][0] if i + 1 < len(pr) else dur) - t)
    main_bw = max(bw_ms, key=bw_ms.get) if bw_ms else 160
    sc, e = [], 0
    for s in R['scStart']:
        while e < len(R['scEnd']) and R['scEnd'][e][0] < s[0]:
            e += 1
        en = R['scEnd'][e] if e < len(R['scEnd']) else None
        te = en[0] if en else s[0]
        tries = sum(1 for a in (R['colTry'], R['bwTry']) for z in a if s[0] <= z[0] <= te)
        frm, to = s[2], en[1] if en else None
        sc.append(dict(ts=s[0] - t0, te=te - t0, blocked=tries == 0 and te - s[0] < 0.5,
                       wide=bool(frm and to and to['bw'] > frm['bw'])))
        if en:
            e += 1
    return dict(src=R.get('src', '?'), band=R.get('band'), dur=dur, bins=bins, rates=rates, bw_ms=bw_ms,
                main_bw=main_bw, max_bw=max([x[3] for x in tx] + [r['bw'] for _, r in pr]),
                max_nss=max([x[2] for x in tx] + [r['nss'] for _, r in pr]), sc=sc)


def fit(T):
    """Same as the playground's fitTrace(): SNR from SISO short-GI rates at <= main BW, then MIMO and long-GI
    (1.6/3.2 us, on the 3.2 us curves) SNR penalties, then obss<bw> for wider BWs."""
    def rate(key):
        bw, nss, mcs, gi = key
        return Rate(mcs, nss, bw, gi in (0, 2))

    def pick(f):
        return [(k, v) for k, v in T['rates'].items()
                if k[0] <= T['main_bw'] and v[0] >= 40 and has_rate(rate(k)) and f(k)]

    def sse(rs, s):
        w = sum(v[0] for _, v in rs) or 1
        return sum(v[0] * (v[1] / v[0] - (1 - phy_per(rate(k), s))) ** 2 for k, v in rs) / w

    def scan(lo, hi, f):
        grid = [(lo + i / 4, f(lo + i / 4)) for i in range(int((hi - lo) * 4) + 1)]
        best = min(e for _, e in grid)
        flat = [x for x, e in grid if e <= best + 1e-4]
        return flat[len(flat) // 2], best

    short = lambda k: k[3] in (0, 2)
    siso = pick(lambda k: k[1] == 1 and short(k))
    mimo = pick(lambda k: k[1] == 2 and short(k))
    lgi = pick(lambda k: k[1] == 1 and not short(k))
    snr, best = scan(-10, 55, lambda s: sse(siso or pick(lambda k: True), s))
    mimo_db = scan(0, 15, lambda p: sse(mimo, snr - p))[0] if mimo else 0.0
    lgi_db = scan(0, 15, lambda p: sse(lgi, snr - p))[0] if lgi else 0.0

    def pen(k):
        return (mimo_db if k[1] >= 2 else 0.0) + (0.0 if short(k) else lgi_db)
    col = 0.0
    if siso:
        k, v = max(siso, key=lambda kv: kv[1][0])
        p = 1 - phy_per(rate(k), snr)
        if p > 0.5:
            col = max(0.0, min(0.5, 1 - (v[1] / v[0]) / p))
    obss = {}
    for bw in [b for b in BANDWIDTHS if b > T['main_bw']]:
        rs = [(k, v) for k, v in T['rates'].items() if k[0] == bw and has_rate(rate(k))]
        n = sum(v[0] for _, v in rs)
        if n < 40:
            continue
        ok = sum(v[1] for _, v in rs)
        pr = sum(v[0] * (1 - phy_per(rate(k), snr - pen(k))) * (1 - col) for k, v in rs)
        if pr / n < 0.05:
            continue
        p = 1 - (ok / n) / (pr / n)
        if p > 0.02:
            obss[bw] = round(min(0.98, p), 2)
    return dict(snr=round(snr, 2), col=round(col, 2), obss=obss, mimo=mimo_db, lgi=lgi_db, rms=best ** 0.5)


def drop_stats(bins, thr):
    drop_ms, episodes, run = 0, 0, 0
    for v in bins + [float('inf')]:
        if v < thr:
            drop_ms += 100; run += 1
        else:
            episodes += run >= 2; run = 0
    return drop_ms, episodes


def trace_kpis(T, thr):
    d, ep = drop_stats(T['bins'], thr)
    return dict(avg=sum(T['bins']) / len(T['bins']), drop_ms=d, episodes=ep,
                wide_ms=sum(v for b, v in T['bw_ms'].items() if b > T['main_bw']),
                wide=sum(s['wide'] for s in T['sc']), blocked=sum(s['blocked'] for s in T['sc']))


def sim_kpis(res, total, thr, ref_bw):
    nb = max(1, int(-(-total // 100)))
    acc = [0.0] * nb
    for r in res.records:
        a, b = r.t_ms, min(total, r.t_ms + r.dt_ms)
        while a < b:
            k = int(a // 100); e = min(b, (k + 1) * 100)
            if k < nb:
                acc[k] += r.tpt * (e - a)
            a = e
    bins = [v / min(100, total - i * 100) for i, v in enumerate(acc)]
    d, ep = drop_stats(bins, thr)
    tw = sum(r.tpt * r.dt_ms for r in res.records); ts = sum(r.dt_ms for r in res.records) or 1
    ev = res.events
    return dict(avg=tw / ts, drop_ms=d, episodes=ep,
                wide_ms=sum(r.dt_ms for r in res.records if r.state == 'STAY' and r.bw > ref_bw),
                wide=sum(1 for s in ev if not s['blocked'] and s['to'] and s['to'].bw > s['from'].bw),
                blocked=sum(1 for s in ev if s['blocked']))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace')
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--csv', help='write the baseline run (seed 1) to this CSV')
    ap.add_argument('--random-traps', action='store_true',
                    help='random obss loss everywhere instead of the log\'s trap moments (quiet<bw>)')
    ap.add_argument('--gap', type=float, default=5.0, help='quiet-gap length in ms (default 5 = one test window)')
    a = ap.parse_args(argv)

    T = build_trace(load(a.trace))
    F = fit(T)
    luck = [round(s['ts']) for s in T['sc'] if s['wide']]
    quiet = {k: luck for k in F['obss']} if luck and not a.random_traps else None
    ch = Channel([Seg(T['dur'], F['snr'], collision=F['col'], profile='awgn', obss=F['obss'] or None,
                      mimo_db=F['mimo'], lgi_db=F['lgi'], quiet=quiet, quiet_gap_ms=a.gap)])
    cfg = TLCConfig(max_bw=T['max_bw'], max_nss=2 if T['max_nss'] > 1 else 1)
    st0 = ch.state(0)
    init = max(all_rates(cfg.max_bw, cfg.max_nss, cfg.max_mcs), key=lambda r: expected_tpt(r) * (1 - per(r, st0)))
    thr = 0.4 * median(T['bins'])
    ob = ', '.join([f'obss{k}={v}' for k, v in F['obss'].items()]
                   + [f"quiet{k}=" + '/'.join(f'{x / 1000:.2f}' for x in v) for k, v in (quiet or {}).items()]
                   + ([f"mimo={F['mimo']}"] if F['mimo'] else []) + ([f"lgi={F['lgi']}"] if F['lgi'] else []))
    print(f"trace  : {T['src']}  band {T['band']}  {T['dur'] / 1000:.1f} s  main BW {T['main_bw']} (max {T['max_bw']})")
    print(f"fit    : SNR {F['snr']} dB, collision {F['col']}{', ' + ob if ob else ''}  (rms err {F['rms'] * 100:.0f}%)")
    print(f"preset : {round(T['dur'])}, {F['snr']}, -, {F['col']}, awgn{', ' + ob if ob else ''}")
    print(f"drop   : 100 ms bin < {thr:.0f} Mbps (40% of the real median); episode >= 200 ms; {a.seeds} seeds\n")

    rows = [('Real trace', trace_kpis(T, thr))]
    for name, opts in VARIANTS:
        acc = dict(avg=0, drop_ms=0, episodes=0, wide_ms=0, wide=0, blocked=0)
        for s in range(1, a.seeds + 1):
            res = run_sim(ch, ReferenceTLC(init_rate=init, **opts), cfg, seed=s, mc_ppdu=True)
            if a.csv and s == 1 and name.startswith('Current'):
                res.to_csv(a.csv)
            k = sim_kpis(res, T['dur'], thr, T['main_bw'])
            for f in acc:
                acc[f] += k[f] / a.seeds
        rows.append((name, acc))

    hdr = f"{'variant':28} {'avg Mbps':>9} {'drop s':>7} {'drops':>6} {'s>' + str(T['main_bw']):>7} {'wider':>6} {'blocked':>8}"
    print(hdr); print('-' * len(hdr))
    for name, k in rows:
        print(f"{name:28} {k['avg']:9.1f} {k['drop_ms'] / 1000:7.2f} {k['episodes']:6.1f} "
              f"{k['wide_ms'] / 1000:7.2f} {k['wide']:6.1f} {k['blocked']:8.1f}")
    if a.csv:
        print(f"\nbaseline seed-1 run -> {a.csv}")


if __name__ == '__main__':
    sys.exit(main())
