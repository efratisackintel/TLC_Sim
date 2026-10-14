"""Convert a uSniffer/SysMonitor text ``.sysmon`` trace into a compact TLC *replay* JSON.

The replay is loaded by the playground's Simulation tab (``Load sysmon replay``) and overlaid
on the simulated charts, and its RSSI/rate trace is turned into a scenario preset so the
same situation can be re-simulated and A/B-tested against algorithm fixes.

Usage:
    python tools/sysmon_to_replay.py <trace.sysmon> [-o out.json] [--js doc/sysmon_ref.js]

Only the TLC-relevant events are kept (data PPDUs, BA/ACK timeouts, TX_RATE_SCALE, RS_MNG_*,
LQ command, RX RSSI). Times are the trace ``systime`` in ms.
"""
import argparse
import json
import os
import re
import sys

KEEP = {
    'TX_DATA_FRAME', 'TX_RATE_SCALE', 'TX_BACK_TIMEOUT', 'TX_ACK_CTS_TIMEOUT',
    'RS_MNG_STATISTICS', 'RS_MNG_SCALE_ACTION', 'RS_MNG_SEARCH_CYCLE_START',
    'RS_MNG_SEARCH_CYCLE_END', 'RS_MNG_TRY_COLUMN_SWITCH', 'RS_MNG_SEARCH_COL_DECISION',
    'RS_MNG_TRY_BW_SWITCH', 'TLC', 'RX_RSSI', 'RX_CTL_FRAME',
}
BW_CODE = {0: 20, 1: 40, 2: 80, 3: 160, 4: 320}
_kv = re.compile(r'([A-Za-z_][\w]*)\s+([^,]+)')


def parse_decoded(s):
    """'staId 0, rateIndex 2, LDPC, mimo' -> {'staId':'0','rateIndex':'2','LDPC':True,'mimo':True}."""
    out = {}
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        m = _kv.fullmatch(part)
        if m:
            out[m.group(1)] = m.group(2).strip()
        else:
            out[part] = True
    return out


def num(v):
    """'0x3d' / '61' / '160MHz (0x3)' / 'STAY (0x0)' -> int (the hex in parentheses wins)."""
    if v is None or v is True:
        return None
    m = re.search(r'\(0x([0-9a-fA-F]+)\)', v)
    if m:
        return int(m.group(1), 16)
    v = v.split()[0]
    try:
        return int(v, 16) if v.lower().startswith('0x') else int(v)
    except ValueError:
        return None


def label(v):
    """'STAY (0x0)' -> 'STAY'."""
    return v.split(' (')[0] if isinstance(v, str) else v


def decode_rate(d):
    """Decoded rate dict -> {mcs,nss,bw,gi,ant,mod} (EHT/HE: mcs = rate_code & 0xF)."""
    if not d or 'rate_code' not in d:
        return None
    rc = num(d['rate_code']) or 0
    mod = label(d.get('type_mod', ''))
    legacy = mod in ('ofdm', 'cck')
    return {
        'mcs': rc if legacy else rc & 0xF,
        'nss': 2 if d.get('mimo') else 1,
        'bw': BW_CODE.get(num(d.get('BW')) or 0, 20),
        'gi': num(d.get('gi_ltf')) or 0,
        'ant': num(d.get('ant_sel')) or 0,
        'mod': mod,
    }


def events(path):
    """Yield (name, t_ms, {field: decoded_dict}) for every KEEP event in the trace."""
    name = None
    t = None
    fields = {}
    with open(path, encoding='ascii', errors='replace') as f:
        for line in f:
            if line[:1].isdigit() and '\t' in line:
                if name in KEEP:
                    yield name, t, fields
                hdr = line.rstrip().split('\t', 1)[1].split(' ')
                name = hdr[1] if len(hdr) > 1 else None
                t = None
                fields = {}
                continue
            if name not in KEEP:
                continue
            p = line.rstrip('\r\n').split('\t')
            if len(p) >= 5 and p[3] == 'systime':
                try:
                    t = float(p[4].rstrip(','))
                except ValueError:
                    pass
            elif len(p) >= 6:
                fields[p[3].strip()] = parse_decoded(p[5])
        if name in KEEP:
            yield name, t, fields


def convert(path):
    R = {'src': os.path.basename(path), 'band': None, 'tx': [], 'rs': [], 'baTo': [], 'ackTo': [], 'stats': [],
         'act': [], 'scStart': [], 'scEnd': [], 'colTry': [], 'colDec': [], 'bwTry': [], 'lq': [],
         'rssi': []}
    for name, t, F in events(path):
        if t is None:
            continue
        t = round(t, 3)
        if name == 'TX_DATA_FRAME':
            r = decode_rate(F.get('frame_rate'))
            tfd = F.get('tfd_info', {})
            if not r or r['mod'] not in ('ofdm_eht', 'ofdm_he'):
                continue
            ft = F.get('frame_time_n_cnt', {})
            R['tx'].append([t, r['mcs'], r['nss'], r['bw'], r['gi'], r['ant'],
                            num(ft.get('frame_cnt')), num(F.get('byte_cnt', {}).get('byte_cnt')),
                            num(ft.get('frame_time')), 1 if tfd.get('SCD_1ST_TIME') else 0,
                            num(tfd.get('ScdQueue'))])
        elif name == 'TX_RATE_SCALE':
            p0, p1 = F.get('params0', {}), F.get('params1', {})
            R['rs'].append([t, num(p0.get('rateIndex')), num(p0.get('success')),
                            num(p1.get('txed_vs_acked'))])
        elif name == 'TX_BACK_TIMEOUT':
            R['baTo'].append(t)
        elif name == 'TX_ACK_CTS_TIMEOUT':
            R['ackTo'].append(t)
        elif name == 'RS_MNG_STATISTICS':
            pr, al = F.get('primaryRateStats', {}), F.get('allRateStats', {})
            R['stats'].append([t, num(pr.get('txed')), num(pr.get('acked')), num(al.get('txed')),
                               num(al.get('acked')),
                               num(F.get('currentSR', {}).get('success_ratio')),
                               num(F.get('currentAvgTpt', {}).get('average_tpt')),
                               num(F.get('totalFramesSuccess', {}).get('total_success_frames')),
                               num(F.get('totalFramesFailed', {}).get('total_failed_frames'))])
        elif name == 'RS_MNG_SCALE_ACTION':
            ar = F.get('actionAndReason', {})
            R['act'].append([t, label(ar.get('action')), label(ar.get('reason')),
                             num(F.get('currTpt', {}).get('currTpt')),
                             num(F.get('lowTpt', {}).get('lowTpt')),
                             num(F.get('highTpt', {}).get('highTpt')),
                             num(F.get('currSuccessRatio', {}).get('currSuccessRatio'))])
        elif name == 'RS_MNG_SEARCH_CYCLE_START':
            sp = F.get('searchCycleParams', {})
            R['scStart'].append([t, num(sp.get('startReason')), decode_rate(F.get('lastStableRate'))])
        elif name == 'RS_MNG_SEARCH_CYCLE_END':
            R['scEnd'].append([t, decode_rate(F.get('newStableRate'))])
        elif name == 'RS_MNG_TRY_COLUMN_SWITCH':
            cp = F.get('colSwitchParams', {})
            R['colTry'].append([t, label(cp.get('colId')), decode_rate(F.get('currRate')),
                                decode_rate(F.get('newRate')),
                                num(F.get('currTpt', {}).get('curr_tpt')),
                                num(F.get('newRateExpectedTpt', {}).get('new_rate_expected_tpt'))])
        elif name == 'RS_MNG_SEARCH_COL_DECISION':
            sp = F.get('searchColParams', {})
            R['colDec'].append([t, label(sp.get('colId')), label(sp.get('decision')),
                                decode_rate(F.get('stableRate')),
                                num(F.get('stableRateTpt', {}).get('stable_rate_tpt')),
                                decode_rate(F.get('testRate')),
                                num(F.get('testRateTpt', {}).get('new_rate_tpt'))])
        elif name == 'RS_MNG_TRY_BW_SWITCH':
            bp = F.get('bwSwitchParams', {})
            R['bwTry'].append([t, BW_CODE.get(num(bp.get('old_bw'))), BW_CODE.get(num(bp.get('new_bw'))),
                               label(bp.get('colId'))])
        elif name == 'TLC':
            fl = F.get('tlc_flags_rts_bit_msk', {})
            R['lq'].append([t, decode_rate(F.get('rate0')), decode_rate(F.get('rate1')),
                            1 if fl.get('test_window') else 0])
        elif name == 'RX_RSSI':
            rs = F.get('rssi', {})
            a, b = num(rs.get('inband_a')), num(rs.get('inband_b'))
            if a is not None and b is not None:
                R['rssi'].append([t, a, b])
        elif name == 'RX_CTL_FRAME' and not R['band']:
            R['band'] = label(F.get('phy_flags', {}).get('band')) or None
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace')
    ap.add_argument('-o', '--out', help='output JSON (default: <trace>.replay.json next to the trace)')
    ap.add_argument('--js', help='also write a JS bundle (const SYSMON_REF=...) for file:// use')
    a = ap.parse_args(argv)
    R = convert(a.trace)
    out = a.out or os.path.splitext(a.trace)[0] + '.replay.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(R, f, separators=(',', ':'))
    print(f'{out}: ' + ', '.join(f'{k}={len(v)}' for k, v in R.items() if isinstance(v, list)))
    if a.js:
        with open(a.js, 'w', encoding='utf-8') as f:
            f.write('// Generated by tools/sysmon_to_replay.py from ' + R['src'] + '\n')
            f.write('const SYSMON_REF = ' + json.dumps(R, separators=(',', ':')) + ';\n')
        print(f'{a.js} written')


if __name__ == '__main__':
    sys.exit(main())
