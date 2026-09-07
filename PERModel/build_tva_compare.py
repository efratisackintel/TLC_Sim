"""Generate TVA sim-vs-lab comparison workbooks (one per Max BW).

Runs the TLC rate-scale simulation (a Python port of the playground engine) over the
TVA SNR sweep, compares each step against the matching lab SCD "sum" JSON in
PERModel/RefTVA (auto-picked by bandwidth, MCS-knee aligned), and writes an .xlsx per
bandwidth into Results/ with:
  - TVA        : per-step table (sim/PR blue, genie purple, lab green) + lab source path
  - Charts     : 5 line charts (throughput, MCS, BW, GI, streams) sim vs genie vs lab
  - RSSI to SNR: NF=4 + 8 dB margin worked example

The throughput tables (EXP_TPT_HE) are the firmware `expectedTptHe` values (Mbps x10);
PER curves come from doc/per_lut.js. Channel is AWGN (matches the conducted lab setup).

Usage:  python PERModel/build_tva_compare.py
"""
import json, re, math, os
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.marker import Marker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'Results')
REFDIR = os.path.join(ROOT, 'PERModel', 'RefTVA')

LUT = json.loads(re.search(r'\{.*\}', open(os.path.join(ROOT, 'doc', 'per_lut.js'), encoding='utf-8').read(), re.S).group(0))

# Firmware expectedTptHe (Mbps x10): [BW]['08'|'32' GI][NSS 1|2] -> MCS 0..13
EXP_TPT_HE = {
 20:{'32':{1:[62,124,186,248,372,497,559,621,745,828,932,1035,1060,1170],2:[124,248,372,497,745,994,1118,1243,1491,1657,1864,2071,2030,2350]},
     '08':{1:[73,146,219,292,438,585,658,731,877,975,1096,1218,1230,1360],2:[146,292,438,585,877,1170,1316,1462,1755,1950,2193,2437,2480,2750]}},
 40:{'32':{1:[124,248,372,497,745,994,1118,1243,1491,1657,1864,2071,2230,2460],2:[248,497,745,994,1491,1989,2237,2486,2983,3315,3729,4143,4270,4950]},
     '08':{1:[146,292,438,585,877,1170,1316,1462,1755,1950,2193,2437,2600,2870],2:[292,585,877,1170,1755,2340,2632,2925,3510,3900,4387,4875,5230,5780]}},
 80:{'32':{1:[260,520,780,1041,1561,2082,2342,2603,3123,3470,3904,4338,4690,5180],2:[520,1041,1561,2082,3123,4165,4685,5206,6247,6941,7809,8677,9000,10430]},
     '08':{1:[306,612,918,1225,1837,2450,2756,3062,3675,4083,4593,5104,5470,6040],2:[612,1225,1837,2450,3675,4900,5512,6125,7350,8166,9187,10208,11010,12170]}},
 160:{'32':{1:[520,1041,1561,2082,3123,4165,4685,5206,6247,6941,7809,8677,9870,10900],2:[1041,2082,3123,4165,6247,8330,9371,10412,12495,13883,15618,17354,18940,21960]},
      '08':{1:[612,1225,1837,2450,3675,4900,5512,6125,7350,8166,9187,10208,11520,12720],2:[1225,2450,3675,4900,7350,9800,11025,12250,14700,16333,18375,20416,23179,25630]}},
 320:{'32':{1:[1140,2260,3380,5260,6660,8810,9870,10900,12960,14320,15990,17630,18940,19320],2:[2180,4250,6660,8810,12960,16980,18940,21960,26110,28800,32190,35430,38080,43380]},
      '08':{1:[1340,2660,3970,5260,7800,10300,11520,12720,15110,16670,18600,21260,23170,25630],2:[2570,4930,7800,10300,15110,20720,23170,25630,30430,33540,37200,42520,45720,50400]}},
}
BANDWIDTHS = [20, 40, 80, 160, 320]
ISI_PEN, ISI_FLOOR_MAX, ISI_FLOOR_SCALE = 6.0, 0.5, 1.0

def peakTpt(mcs, nss, bw, gi08):
    t = EXP_TPT_HE.get(bw)
    if not t: return 0
    arr = t['08' if gi08 else '32'][2 if nss >= 2 else 1]
    return arr[mcs] / 10 if 0 <= mcs < len(arr) else 0

def isi(gi_us, tau):
    if tau <= 0 or gi_us <= 0: return (0, 0)
    ex = tau / gi_us - 1
    if ex <= 0: return (0, 0)
    return (ISI_PEN * ex, ISI_FLOOR_MAX * (1 - math.exp(-ex / ISI_FLOOR_SCALE)))

def perLookup(bw, mcs, nss, gi08, snr, tau):
    e = LUT.get(f"{bw},{mcs},{nss},{1 if gi08 else 0}")
    if not e: return 1.0
    pen, floor = isi(0.8 if gi08 else 3.2, tau)
    sE = snr - pen
    s, p, n = e['s'], e['p'], len(e['s'])
    if sE < s[0]: per = 1.0
    elif sE > s[-1]: per = 0.0
    else:
        per = p[-1]
        for i in range(1, n):
            if sE <= s[i]:
                tt = (sE - s[i-1]) / (s[i] - s[i-1]); per = p[i-1] + tt * (p[i] - p[i-1]); break
    return max(per, floor)

def retryChain(p, base):
    b = base or p
    chain = [dict(bw=p['bw'], mcs=p['mcs'], nss=p['nss'], gi08=p['gi08'])]
    same = b['bw'] == p['bw'] and b['mcs'] == p['mcs'] and b['nss'] == p['nss'] and b['gi08'] == p['gi08']
    if not same: chain.append(dict(bw=b['bw'], mcs=b['mcs'], nss=b['nss'], gi08=b['gi08']))
    if b['mcs'] >= 1: chain.append(dict(bw=b['bw'], mcs=b['mcs']-1, nss=b['nss'], gi08=b['gi08']))
    if b['mcs'] >= 2: chain.append(dict(bw=b['bw'], mcs=b['mcs']-2, nss=b['nss'], gi08=b['gi08']))
    chain.append(dict(bw=b['bw'], mcs=0, nss=1, gi08=False))
    chain.append(dict(bw=20, mcs=0, nss=1, gi08=False))
    return chain

def retryTput(p, base, snr, col, frameBits, tau):
    chain = retryChain(p, base); reach = 1.0; eT = 0.0; deliv = 0.0
    for r in chain:
        per = perLookup(r['bw'], r['mcs'], r['nss'], r['gi08'], snr, tau); fail = 1 - (1-per) * (1-col)
        phy = peakTpt(r['mcs'], r['nss'], r['bw'], r['gi08']); tR = frameBits / (phy*1e6) if phy > 0 else 1e6
        eT += reach * tR; deliv += reach * (1-fail); reach *= fail
        if reach < 1e-4: break
    tput = deliv * frameBits / eT / 1e6 if eT > 0 else 0
    return tput, eT

def make_bestCand(maxBw, maxNss, MAXM, tau):
    cands = [(b, nn, m, g) for b in [x for x in BANDWIDTHS if x <= maxBw]
             for nn in range(maxNss, 0, -1) for m in range(MAXM+1) for g in (True, False)]
    memo = {}
    def f(snr):
        key = round(snr*2) / 2
        if key not in memo:
            bt = -1; win = None
            for (b, nn, m, g) in cands:
                e = peakTpt(m, nn, b, g) * (1 - perLookup(b, m, nn, g, snr, tau))
                if e > bt: bt = e; win = dict(tpt=e, mcs=m, bw=b, nss=nn, gi=g)
            memo[key] = win
        return memo[key]
    return f

class TLC:
    def __init__(self, maxBw, maxNss, MAXM, seed):
        self.bws = [b for b in BANDWIDTHS if b <= maxBw]; self.nssOpts = [1, 2] if maxNss >= 2 else [1]; self.MAXM = MAXM
        self.C = dict(PERF=.95, NODEC=.90, FORCE=.15, SEARCH=20, DWELL=2000, EWMA=.4, SUCC=4500, FAIL=400, GUARD=300, UPGUARD=200, IGNORE=1000, STALE=300)
        self.col = [1, self.bws[0], True]; self.mcs = 0; self.sr = {}; self.srT = {}
        self.state = 'STAY'; self.mode = 'search'; self.succ = 0; self.fail = 0; self.lastEnd = -1e9
        self.lastReason = None; self.pending = None; self.sq = []; self.best = None; self.target = 0; self.stayPeak = 0
        self.nextUp = 0; self.avoidMcs = -1; self.avoidUntil = -1e9; self.stableCol = [1, self.bws[0], True]; self.stableMcs = 0
        if seed: self.col = list(seed['col']); self.mcs = seed['mcs']
        self.goodMcs = self.mcs; self.goodTpt = 0.0   # last MCS that met NODEC (search fallback)
    def key(self, c, m): return f"{c[0]},{c[1]},{1 if c[2] else 0},{m}"
    def avgtpt(self, c, m, s): return s * peakTpt(m, c[0], c[1], c[2])
    def bestRateForCol(self, c, tgt):
        for m in range(self.MAXM+1):
            if peakTpt(m, c[0], c[1], c[2]) >= tgt: return m
        return self.MAXM
    def neigh(self):
        n, b, g = self.col; out = []
        for nn in self.nssOpts:
            if nn != n: out.append([nn, b, g])
        i = self.bws.index(b)
        if i+1 < len(self.bws): out.append([n, self.bws[i+1], g])
        if i-1 >= 0: out.append([n, self.bws[i-1], g])
        out.append([n, b, not g]); return out
    def lq(self):
        primary = dict(mcs=self.mcs, nss=self.col[0], bw=self.col[1], gi08=self.col[2])
        stable = dict(mcs=self.stableMcs, nss=self.stableCol[0], bw=self.stableCol[1], gi08=self.stableCol[2]) if self.state == 'SEARCH' else primary
        return dict(primary=primary, stable=stable, thold=self.C['DWELL'] if self.mode == 'dwell' else self.C['SEARCH'], mode=self.mode, state=self.state)
    def enter(self, s, t):
        good = min(self.mcs, self.goodMcs)   # never seed the search on a rate we just watched fail
        self.stableCol = list(self.col); self.stableMcs = good
        self.target = max(self.stayPeak, peakTpt(good, self.col[0], self.col[1], self.col[2]))
        self.best = [list(self.col), good, max(self.goodTpt, self.avgtpt(self.col, good, s))]   # incumbent must be beaten to switch
        self.sq = self.neigh(); self.succ = self.fail = 0; self.state = 'SEARCH'; self.mode = 'search'; self.col = self.sq.pop(0); self.mcs = self.bestRateForCol(self.col, self.target)
    def onStats(self, txed, acked, t):
        C = self.C; k = self.key(self.col, self.mcs); swin = acked / txed
        stale = (k not in self.srT) or (t - self.srT[k]) > C['STALE']
        s = swin if stale else C['EWMA'] * swin + (1 - C['EWMA']) * self.sr[k]
        self.sr[k] = s; self.srT[k] = t; self.succ += acked; self.fail += txed - acked
        if self.state == 'STAY':
            if s >= C['NODEC']:
                self.stayPeak = max(self.stayPeak, peakTpt(self.mcs, self.col[0], self.col[1], self.col[2]))
                self.goodMcs = self.mcs; self.goodTpt = self.avgtpt(self.col, self.mcs, s)   # remember last known-good rate
            held = False
            if s < C['FORCE'] or (s < C['NODEC'] and self.mcs > 0):
                if self.mcs > 0: self.avoidMcs = self.mcs; self.avoidUntil = t + C['IGNORE']; self.mcs -= 1
            elif s >= C['PERF'] and self.mcs < self.MAXM:
                up = self.mcs + 1
                if (up == self.avoidMcs and t < self.avoidUntil) or t < self.nextUp: held = True
                else: self.mcs = up; self.nextUp = t + C['UPGUARD']
            else: held = True
            self.mode = 'dwell' if held else 'search'
            reason = None
            if self.succ > C['SUCC']:
                if self.lastReason == 'FAIL': reason = 'SUCCESS'
                elif t - self.lastEnd > C['GUARD']: reason = 'SUCCESS'
            if reason is None and self.fail > C['FAIL']: reason = 'FAIL'
            if reason is not None: self.pending = reason; self.enter(s, t)
        else:
            cand = self.avgtpt(self.col, self.mcs, s)
            if cand > self.best[2]: self.best = [list(self.col), self.mcs, cand]
            if self.sq:
                self.col = self.sq.pop(0); self.mcs = self.bestRateForCol(self.col, self.target); self.mode = 'search'
            else:
                self.col = self.best[0]; self.mcs = self.best[1]; self.state = 'STAY'; self.succ = self.fail = 0; self.stayPeak = 0
                self.lastReason = self.pending; self.lastEnd = t; self.mode = 'dwell'
        return self.lq()

def alignOffset(sim_pts, lab_pts):
    """Robust RSSI->SNR offset: median over per-MCS transitions, excluding the
    saturated top-MCS plateau (whose width differs between sim and lab) and
    start-up artifacts. sim_pts=[(snr,mcs)], lab_pts=[(rssi,mcs)]."""
    from statistics import median, mean
    simByM, labByM = {}, {}
    for snr, m in sim_pts:
        if m is not None: simByM.setdefault(m, []).append(snr)
    for rssi, m in lab_pts:
        if m is not None: labByM.setdefault(m, []).append(rssi)
    if not simByM or not labByM: return None
    maxM = max(max(simByM), max(labByM))
    offs = [mean(simByM[m]) - mean(labByM[m]) for m in sorted(set(simByM) & set(labByM)) if m != maxM]
    return median(offs) if offs else None

def parseLabRate(s):
    m = re.search(r'MCS(\d+)', s, re.I); b = re.search(r'(\d+)MHz', s, re.I)
    return dict(mcs=int(m.group(1)) if m else None, bw=int(b.group(1)) if b else None,
                nss=2 if re.search('MIMO', s, re.I) else (1 if re.search('SISO', s, re.I) else None),
                gi08=False if re.search('LTF3', s, re.I) else True)

def parseLabSum(j):
    out = []; arr = (j or {}).get('data') or []
    el = next((x for x in arr if x and x.get('resource') == 'dut'), arr[0] if arr else None)
    steps = el and el.get('data')
    if not steps: return out
    for k in sorted(steps, key=lambda x: int(x)):
        s = steps[k]
        try: res = s['UplinkFwDataPathAnalysis']['results']['dut']['results'][0]
        except Exception: continue
        rates = res.get('rates', {}); dom = None; cnt = -1; succ = None
        for rk, rv in rates.items():
            if rk == 'TOTAL': continue
            if isinstance(rv, dict) and isinstance(rv.get('count'), (int, float)) and rv['count'] > cnt:
                cnt = rv['count']; dom = rk; succ = rv.get('avg_success')
        rp = parseLabRate(dom) if dom else {}
        rssi = None
        try:
            a = res['rssi']['rssi_bcn_a']['average']
            if a is not None: rssi = -a
        except Exception: pass
        out.append(dict(idx=int(k), tpt=s.get('tpt'), rssi=rssi, sr=succ,
                        mcs=rp.get('mcs'), bw=rp.get('bw'), nss=rp.get('nss'), gi08=rp.get('gi08'), rate=dom))
    return out

REF_BY_BW = {20: 'tva_11be_20mhz_uhbch69_tx_scd.json', 40: 'tva_11be_40mhz_uhbch69_tx_scd.json',
             80: 'tva_11be_80mhz_uhbch69_tx_scd.json', 160: 'tva_11be_160mhz_uhbch69_tx_scd.json',
             320: 'tva_11be_320mhz_uhbch5_tx_scd.json'}
SNRS = [44, 41, 38, 35, 32, 29, 26, 23, 20, 17, 14, 11, 8, 5, 2]

def run_bw(bw, tau=0.0, maxNss=2, MAXM=13):
    total = len(SNRS) * 1000
    bestCand = make_bestCand(bw, maxNss, MAXM, tau)
    bcd0 = bestCand(SNRS[0])
    seed = dict(col=[bcd0['nss'], bcd0['bw'], bcd0['gi']], mcs=max(0, bcd0['mcs']))
    tlc = TLC(bw, maxNss, MAXM, seed); lq = tlc.lq(); t = 0.0; frame = 1500; g = 0
    per_step = {}
    C = tlc.C
    while t < total and g < 80000:
        g += 1; snr = SNRS[min(int(t // 1000), len(SNRS)-1)]; N = lq['thold']; p = lq['primary']
        per = perLookup(p['bw'], p['mcs'], p['nss'], p['gi08'], snr, tau); swin = (1 - per)
        # FW aborts a failing rate within a few stat updates, not a full optimal window
        if lq['mode'] == 'dwell' and swin < C['FORCE']: N = C['SEARCH']
        acked = round(N * swin)
        tput, eT = retryTput(p, lq['stable'], snr, 0, frame*8, tau); dt = max(N * eT * 1000, 0.02)
        bcd = bestCand(snr); step = int(t // 1000)
        per_step.setdefault(step, []).append(dict(dt=dt, tput=tput, sr=swin, best=bcd['tpt'],
            prMcs=p['mcs'], prBw=p['bw'], prNss=p['nss'], prGi08=p['gi08'],
            geMcs=bcd['mcs'], geBw=bcd['bw'], geNss=bcd['nss'], geGi08=bcd['gi']))
        lq = tlc.onStats(N, acked, t); t += dt
    def dominant(recs, keyf):
        agg = {}
        for r in recs: agg[keyf(r)] = agg.get(keyf(r), 0) + r['dt']
        return max(agg.items(), key=lambda kv: kv[1])
    rows = []
    for step in sorted(per_step):
        recs = per_step[step]; sd = sum(r['dt'] for r in recs) or 1
        prKey, prDt = dominant(recs, lambda r: (r['prMcs'], r['prBw'], r['prNss'], r['prGi08']))
        geKey, _ = dominant(recs, lambda r: (r['geMcs'], r['geBw'], r['geNss'], r['geGi08']))
        rows.append(dict(step=step+1, snr=SNRS[step],
            prTpt=sum(r['tput']*r['dt'] for r in recs)/sd, prSR=sum(r['sr']*r['dt'] for r in recs)/sd,
            prPct=round(prDt/sd*100), geTpt=sum(r['best']*r['dt'] for r in recs)/sd,
            prMcs=prKey[0], prBw=prKey[1], prNss=prKey[2], prGi08=prKey[3],
            geMcs=geKey[0], geBw=geKey[1], geNss=geKey[2], geGi08=geKey[3], lab=None))
    src = os.path.join(REFDIR, REF_BY_BW[bw])
    lab = parseLabSum(json.load(open(src, encoding='utf-8')))
    off = alignOffset([(r['snr'], r['prMcs']) for r in rows],
                      [(L['rssi'], L['mcs']) for L in lab if L['rssi'] is not None])
    if off is None: off = 62.0
    for r in rows:
        best = None; bd = 1e9
        for L in lab:
            if L['rssi'] is None: continue
            dd = abs((L['rssi'] + off) - r['snr'])
            if dd < bd: bd = dd; best = L
        r['lab'] = best if (best and bd <= 3) else None
    return rows, off, src

FILL = {'s': 'E3F0FB', 'g': 'EFE7FB', 'l': 'E2F1E9', 'sh': 'BFDCF3', 'gh': 'D9C9F5', 'lh': 'C7E4D3', 'dh': 'E2E8F0'}
FCOL = {'s': '0B4F86', 'g': '5B21B6', 'l': '1F6B45', 'd': '334155'}
_thin = Side(style='thin', color='D5DBE3'); BORD = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
def nssTxt(n): return 'MIMO' if n == 2 else ('SISO' if n == 1 else '—')
def giTxt(g): return '0.8µs' if g else '3.2µs'

def write_xlsx(bw, rows, off, lab_src, path):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'TVA'
    cols = [('#', 'd', lambda r: r['step']), ('SNR (dB)', 'd', lambda r: r['snr']),
        ('avg tpt (Mbps)', 's', lambda r: round(r['prTpt'])), ('PR MCS', 's', lambda r: r['prMcs']), ('PR BW', 's', lambda r: r['prBw']),
        ('PR streams', 's', lambda r: nssTxt(r['prNss'])), ('PR GI', 's', lambda r: giTxt(r['prGi08'])),
        ('PR SR', 's', lambda r: f"{round(r['prSR']*100)}%"), ('PR %time', 's', lambda r: f"{r['prPct']}%"),
        ('genie tpt (Mbps)', 'g', lambda r: round(r['geTpt'])), ('genie MCS', 'g', lambda r: r['geMcs']), ('genie BW', 'g', lambda r: r['geBw']),
        ('genie streams', 'g', lambda r: nssTxt(r['geNss'])), ('genie GI', 'g', lambda r: giTxt(r['geGi08'])),
        ('log RSSI', 'l', lambda r: round(r['lab']['rssi'], 1) if r['lab'] else ''),
        ('log tpt (Mbps)', 'l', lambda r: round(r['lab']['tpt']) if r['lab'] and r['lab']['tpt'] is not None else ''),
        ('log MCS', 'l', lambda r: r['lab']['mcs'] if r['lab'] and r['lab']['mcs'] is not None else ''),
        ('log BW', 'l', lambda r: r['lab']['bw'] if r['lab'] and r['lab']['bw'] is not None else ''),
        ('log streams', 'l', lambda r: nssTxt(r['lab']['nss']) if r['lab'] else ''),
        ('log GI', 'l', lambda r: giTxt(r['lab']['gi08']) if r['lab'] and r['lab']['gi08'] is not None else ''),
        ('log SR', 'l', lambda r: f"{round(r['lab']['sr']*100)}%" if r['lab'] and r['lab']['sr'] is not None else '')]
    ws.append([f'Lab log source: {lab_src}    |    RSSI\u2192SNR offset (MCS-knee aligned): {round(off,1)} dB'])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
    ws.cell(1, 1).font = Font(italic=True, color='FF1F6B45')
    ws.append([c[0] for c in cols])
    for i, c in enumerate(cols, 1):
        cell = ws.cell(2, i); cell.fill = PatternFill('solid', fgColor=FILL.get(c[1]+'h', FILL['dh']))
        cell.font = Font(bold=True, color='FF'+FCOL.get(c[1], FCOL['d'])); cell.alignment = Alignment('center', 'center', wrap_text=True); cell.border = BORD
    for r in rows:
        ws.append([c[2](r) for c in cols]); rr = ws.max_row
        for i, c in enumerate(cols, 1):
            cell = ws.cell(rr, i); cell.alignment = Alignment(horizontal='center'); cell.border = BORD
            if c[1] != 'd': cell.fill = PatternFill('solid', fgColor=FILL[c[1]])
            cell.font = Font(color='FF'+FCOL.get(c[1], FCOL['d']))
    for i, w in enumerate([5,9,14,8,7,11,8,7,9,16,10,9,13,9,9,14,9,8,11,8,8], 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = 'A3'
    # ChartData (hidden) + Charts
    cd = wb.create_sheet('ChartData'); cd.sheet_state = 'hidden'
    cd.append(['SNR', 'sim tpt', 'genie tpt', 'lab tpt', 'sim MCS', 'genie MCS', 'lab MCS',
               'sim BW', 'genie BW', 'lab BW', 'sim GI', 'genie GI', 'lab GI', 'sim streams', 'genie streams', 'lab streams'])
    for r in rows:
        L = r['lab']
        cd.append([r['snr'], round(r['prTpt']), round(r['geTpt']), (round(L['tpt']) if L and L['tpt'] is not None else None),
            r['prMcs'], r['geMcs'], (L['mcs'] if L else None),
            r['prBw'], r['geBw'], (L['bw'] if L else None),
            (0.8 if r['prGi08'] else 3.2), (0.8 if r['geGi08'] else 3.2), ((0.8 if L['gi08'] else 3.2) if L and L['gi08'] is not None else None),
            r['prNss'], r['geNss'], (L['nss'] if L else None)])
    n = len(rows); ch_ws = wb.create_sheet('Charts')
    cats = Reference(cd, min_col=1, min_row=2, max_row=1+n)
    syms = ['x', 'square', 'circle']; lines = ['0071C5', '7C3AED', '2E8B57']
    def mkchart(title, c3, anchor):
        ch = LineChart(); ch.title = title; ch.height = 8.5; ch.width = 20; ch.x_axis.title = 'SNR (dB)'; ch.x_axis.delete = False; ch.y_axis.delete = False
        for col in c3:
            ch.add_data(Reference(cd, min_col=col, min_row=1, max_row=1+n), titles_from_data=True)
        ch.set_categories(cats)
        for si, ser in enumerate(ch.series):
            ser.graphicalProperties.line.solidFill = lines[si]; ser.graphicalProperties.line.width = 20000
            ser.marker = Marker(symbol=syms[si], size=6); ser.smooth = False
        ch_ws.add_chart(ch, anchor)
    mkchart('Throughput (Mbps) — sim vs genie vs lab', [2, 3, 4], 'A1')
    mkchart('MCS — sim vs genie vs lab', [5, 6, 7], 'A18')
    mkchart('Bandwidth (MHz) — sim vs genie vs lab', [8, 9, 10], 'A35')
    mkchart('Guard interval (µs) — sim vs genie vs lab', [11, 12, 13], 'A52')
    mkchart('Streams (SISO=1 / MIMO=2) — sim vs genie vs lab', [14, 15, 16], 'A69')
    # RSSI to SNR sheet
    rs = wb.create_sheet('RSSI to SNR')
    NF = 4; MARGIN = 8; reqSnr = 37.0; model = {320: -40, 160: -42, 80: -44.5, 40: -47.5, 20: -50.5}
    rs.append(['SNR \u2192 RSSI \u2014 worked example (EHT, 0.8\u00b5s GI, MCS13)'])
    rs.append(['Noise Floor = \u2212174 + 10\u00b7log10(BW\u00d710^6) + Noise Figure + RSSI implementation Margin ; Estimated RSSI = Noise Floor + required SNR ; RSSI to SNR Diff = \u2212Noise Floor (add to RSSI to get SNR)'])
    rs.append([])
    rs.append(['Noise figure (dB)', 'RSSI implementation Margin (dB)', 'BW (MHz)', 'Noise Floor (dBm)', 'required SNR (dB)', 'Estimated RSSI (dBm)', 'RSSI from model (dBm)', 'RSSI to SNR Diff (dB)'])
    for i in range(1, 9):
        c = rs.cell(4, i); c.fill = PatternFill('solid', fgColor='E2E8F0'); c.font = Font(bold=True); c.alignment = Alignment('center', 'center', wrap_text=True); c.border = BORD
    for i, b in enumerate([320, 160, 80, 40, 20]):
        row = 5 + i
        # NF & Margin are inputs (row 5 only); Noise Floor / RSSI / Diff are live Excel formulas
        rs.append([NF if i == 0 else '', MARGIN if i == 0 else '', b,
                   f'=-174 + 10*LOG10(C{row}*10^6) + $A$5 + $B$5', reqSnr,
                   f'=D{row} + E{row}', model[b], f'=-D{row}'])
        for j in range(1, 9):
            rs.cell(row, j).alignment = Alignment(horizontal='center'); rs.cell(row, j).border = BORD
    for i, w in enumerate([16, 26, 10, 16, 15, 18, 18, 18], 1):
        rs.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    wb.save(path)

def main():
    os.makedirs(OUT, exist_ok=True)
    for bw in BANDWIDTHS:
        rows, off, src = run_bw(bw)
        out = os.path.join(OUT, f'tva_sim_vs_lab_{bw}mhz.xlsx')
        try:
            write_xlsx(bw, rows, off, src, out)
            matched = sum(1 for r in rows if r['lab'])
            print(f"{bw:>3} MHz -> {os.path.basename(out)}  (offset {round(off,1)} dB, {matched}/{len(rows)} lab-matched)")
        except PermissionError:
            print(f"{bw:>3} MHz -> SKIPPED, file is open/locked: {out}")
    print('done ->', OUT)

if __name__ == '__main__':
    main()
