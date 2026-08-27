"""B6 — Simulation Harness / Scheduler: the closed loop + simulated clock."""
from __future__ import annotations
from typing import List, Optional
import random
from .rates import Rate, expected_tpt, all_rates
from .channel import Channel, ChannelState
from .per_model import per, retry_tput
from .emulator import simulate_window
from .tlc import TLC, ReferenceTLC, TLCConfig
from .results import Record, RunResult


def _best_tpt(ch: ChannelState, cands: List[Rate]) -> float:
    """Best achievable effective throughput this window (upper bound for efficiency KPI)."""
    return max(expected_tpt(r) * (1.0 - per(r, ch)) for r in cands)


def run_sim(channel: Channel, tlc: Optional[TLC] = None, config: Optional[TLCConfig] = None,
            frame_bytes: int = 1500, monte_carlo: bool = False, seed: int = 0,
            max_ms: Optional[float] = None) -> RunResult:
    """Run the closed loop over a channel scenario and return the logged result.

    Loop: channel.state -> emulator (stats) -> tlc.on_stats (new rate table) -> log.
    The window size = the stat threshold the TLC requests (search vs dwell); the clock is
    advanced by that window's airtime so the TLC's time-based logic behaves realistically.
    """
    tlc = tlc or ReferenceTLC()
    cfg = config or TLCConfig()
    cands = all_rates(cfg.max_bw, cfg.max_nss, cfg.max_mcs)
    rng = random.Random(seed)

    lq = tlc.configure(cfg)
    t = 0.0
    total = max_ms if max_ms is not None else channel.total_ms
    res = RunResult()

    while t < total:
        ch = channel.state(t)
        stats = simulate_window(lq.rate_table, ch, lq.stat_threshold, monte_carlo, rng)
        p = lq.primary
        tput, e_t, _rty = retry_tput(p, getattr(lq, "stable", None), ch, frame_bytes * 8)   # retry: fallbacks from the stable column
        dt_ms = (lq.stat_threshold * e_t * 1000) if e_t > 0 else 1.0
        res.records.append(Record(t, dt_ms, str(p), p.mcs, p.nss, p.bw, ch.snr_db, ch.collision,
                                  stats.sr, tput, _best_tpt(ch, cands),
                                  getattr(tlc, "mode", "-"), getattr(tlc, "state", "-")))
        lq = tlc.on_stats(stats, t)
        t += dt_ms
    return res
