"""B3 — TX / Statistics Emulator (LMAC + PHY surrogate).

Applies the TLC's rate table against the PER model over a window of frames and returns
aggregated statistics (txed/acked -> Success Ratio). Coarse model: the TLC scales on the
primary rate's success ratio, so we report first-attempt txed/acked of the primary rate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import random
from .rates import Rate, expected_tpt
from .channel import ChannelState
from .per_model import per, phy_fail, retry_chain

AGG_S = 5.4e-3   # RS_MNG_AGG_DURATION_LIMIT: max A-MPDU airtime
OVH_S = 0.5e-3   # per A-MPDU overhead (RTS/CTS, BA, backoff)
FAIL_S = 0.010   # dwell: extra airtime per A-MPDU with no ACK (BA timeout + doubled backoff + RTS); fitted to ZoharBadLog


@dataclass
class WindowStats:
    txed: int
    acked: int

    @property
    def sr(self) -> float:
        return self.acked / self.txed if self.txed else 0.0


def simulate_window(rate_table: List[Rate], ch: ChannelState, window_frames: int,
                    monte_carlo: bool = False,
                    rng: Optional[random.Random] = None) -> WindowStats:
    """Transmit `window_frames` at the primary rate; return first-attempt txed/acked."""
    primary = rate_table[0]
    p = per(primary, ch)
    if monte_carlo:
        rng = rng or random
        acked = sum(1 for _ in range(window_frames) if rng.random() > p)
    else:
        acked = round(window_frames * (1.0 - p))
    return WindowStats(txed=window_frames, acked=acked)


def ppdu_frames(r: Rate, frame_bits: float) -> int:
    """MPDUs that fit in one A-MPDU of AGG_S at this rate. Airtime-limited only: EHT 1024 BA x A-MSDU
    never binds at 5.4 ms (lab TVA: MCS13/320 MIMO = 91% of PHY)."""
    return max(1, int(AGG_S * expected_tpt(r) * 1e6 / frame_bits))


@dataclass
class McWindow:
    stats: WindowStats
    tput: float        # delivered Mbps over the window airtime (incl. retries)
    dt_ms: float       # window airtime
    first_fail: float  # primary-rate failure share


SLOT_MS = (AGG_S + OVH_S) * 1000   # interference timeline resolution (one A-MPDU)


def _slot_rand(seed: int, key: int, slot: int) -> float:
    """Deterministic uniform [0,1) per (seed, source, time slot) - 32-bit integer hash."""
    h = ((seed * 0x9E3779B1) ^ (key * 0x85EBCA77) ^ (slot * 0xC2B2AE3D)) & 0xFFFFFFFF
    h ^= h >> 16
    h = (h * 0x7FEB352D) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x846CA68B) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296.0


OPP_EARLY_MS, OPP_LATE_MS = 300.0, 600.0   # trap-opportunity window around each scripted quiet time


def busy_at(ch: ChannelState, bw: int, t_ms: float, seed: int,
            opp: Optional[dict] = None, dwell: bool = False) -> bool:
    """Interference is external: one fixed busy/free timeline per seed and source (collision for all
    BWs, obss[k] for BW >= k), identical for every TLC variant run with that seed.

    quiet[k] (scripted trap opportunities): wider-BW tests are blocked except one short gap per
    opportunity, opened by the first BW >= k transmission in [t - 300 ms, t + 600 ms]; committed
    (dwell) traffic outside the gap still sees obss[k]. `opp` = per-run state (mirrors busyAt())."""
    s = int(t_ms // SLOT_MS)
    if ch.collision > 0 and _slot_rand(seed, 1, s) < ch.collision:
        return True
    ob = ch.obss or {}
    for k, times in (ch.quiet or {}).items():
        if bw < k:
            continue
        tq = next((x for x in times if x - OPP_EARLY_MS <= t_ms <= x + OPP_LATE_MS), None)
        if tq is not None and opp is not None:
            key = (k, tq)
            if key not in opp:
                opp[key] = t_ms
                opp['last'] = key
            if t_ms < opp[key] + ch.quiet_gap_ms:
                return False
        if not dwell or k not in ob:
            return True
    return any(bw >= k and _slot_rand(seed, 1000 + k, s) < p for k, p in ob.items())


def simulate_window_mc(primary: Rate, stable: Optional[Rate], n: int, ch: ChannelState,
                       frame_bits: float, fail_s: float = 0.0,
                       t0_ms: float = 0.0, seed: int = 1, opp: Optional[dict] = None) -> McWindow:
    """Monte-Carlo window at FW A-MPDU cadence (mirrors the playground's mcWindow()).

    An A-MPDU sent while the medium is busy (busy_at timeline) is wiped, else per-MPDU PHY PER.
    Failed MPDUs walk the retry chain, one A-MPDU (<= AGG_S) per rung. In dwell the initial rate is
    sent twice (RS_MNG_RETRY_TABLE_INITIAL_RATE_NUM=2)."""
    chain = retry_chain(primary, stable)
    if len(chain) > 1 and (stable is None or stable == primary):
        chain.insert(0, chain[0])
    t_r = [frame_bits / (expected_tpt(r) * 1e6) if expected_tpt(r) > 0 else 1.0 for r in chain]
    per_r = [phy_fail(r, ch) for r in chain]
    npp = ppdu_frames(primary, frame_bits)
    acked = deliv = 0
    air = 0.0
    if opp is not None:
        opp['last'] = None

    # every random outcome is keyed by (seed, rate, time slot, MPDU index): same action at the same time -> same result
    def send(k, m):
        nonlocal air
        t_ms, r = t0_ms + air * 1000, chain[k]
        busy = busy_at(ch, r.bw, t_ms, seed, opp, fail_s > 0)
        air += m * t_r[k] + OVH_S
        ok = 0
        if not busy:
            key = 100000 + r.bw * 100 + r.mcs * 4 + r.nss * 2 + (1 if r.gi08 else 0)
            base0 = int(t_ms // SLOT_MS) * 512
            ok = sum(1 for i in range(m) if _slot_rand(seed, key, base0 + i) >= per_r[k])
        if not ok:
            air += fail_s
        return ok
    left = n
    while left > 0:
        m = min(npp, left)
        left -= m
        ok = send(0, m)
        acked += ok
        deliv += ok
        fail = m - ok
        for k in range(1, len(chain)):
            if fail <= 0:
                break
            fit = max(1, min(fail, int(AGG_S / t_r[k])))
            ok2 = send(k, fit)
            deliv += ok2
            fail = fit - ok2
    if opp is not None and opp.get('last') is not None and acked < n / 2:
        del opp[opp['last']]   # quiet gap wasted on a rate that fails anyway: keep the opportunity
    return McWindow(WindowStats(n, acked), deliv * frame_bits / air / 1e6 if air > 0 else 0.0,
                    air * 1000, 1 - acked / n if n else 0.0)
