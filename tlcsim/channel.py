"""B1 — Channel Configuration: time-varying channel state (ground truth).

The channel is expressed in real **SNR (dB)** so it can drive the data-based PER model
directly. Build a Channel from a list of segments; a segment is a constant SNR, or a
linear ramp if `snr_end` is given.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

SNR_MIN, SNR_MAX = -20.0, 60.0

# Named channel profiles -> RMS delay spread (us). Synthetic teaching values, not empirical.
PROFILES = {"awgn": 0.0, "small room": 0.5, "office": 1.0, "outdoor": 3.0}


@dataclass
class ChannelState:
    snr_db: float           # link SNR in dB (higher = cleaner link)
    collision: float        # 0..1 (probability a TX is lost to collision/interference)
    delay_spread_us: float = 0.0  # RMS delay spread (us); 0 = AWGN / no multipath
    obss: Optional[Dict[int, float]] = None  # {bw: P} — A-MPDU at >= bw MHz wiped (bursty, e.g. OBSS on the upper 160)
    mimo_db: float = 0.0    # extra SNR loss for MIMO the AWGN curves miss (fitted from a trace)
    lgi_db: float = 0.0     # extra SNR loss for long GI (1.6/3.2 us) the AWGN curves miss
    quiet: Optional[Dict[int, List[float]]] = None  # {bw: [t_ms..]} scripted wider-BW trap opportunities (see busy_at)
    quiet_gap_ms: float = 5.0

    def loss(self, bw: int) -> float:
        """Whole-transmission loss probability at `bw`: collision combined with every obss[k], k <= bw."""
        ok = 1.0 - self.collision
        for k, p in (self.obss or {}).items():
            if bw >= k:
                ok *= 1.0 - p
        for k in (self.quiet or {}):
            if bw >= k and k not in (self.obss or {}):
                ok = 0.0
        return 1.0 - ok


@dataclass
class Seg:
    """One scenario segment. Constant `snr_db`, or a linear ramp to `snr_end`.

    Delay spread is a channel property (constant over the segment). Give it directly
    via `delay_spread_us`, or by name via `profile` (see PROFILES). `obss` = {bw: P} adds
    bursty whole-A-MPDU loss on the wider channels only (playground token `obss320=P`).
    `quiet` = {bw: [t_ms, ..]} scripts the trap opportunities (playground `quiet320=t1/t2`, `gap=ms`)."""
    ms: float
    snr_db: float
    snr_end: Optional[float] = None
    collision: float = 0.0
    delay_spread_us: float = 0.0
    profile: Optional[str] = None
    obss: Optional[Dict[int, float]] = None
    mimo_db: float = 0.0
    lgi_db: float = 0.0
    quiet: Optional[Dict[int, List[float]]] = None
    quiet_gap_ms: float = 5.0

    def __post_init__(self):
        if self.profile is not None:
            key = self.profile.strip().lower()
            if key not in PROFILES:
                raise ValueError(
                    f"unknown channel profile {self.profile!r}; choose from {list(PROFILES)}")
            self.delay_spread_us = PROFILES[key]


class Channel:
    def __init__(self, segments: Sequence[Seg]):
        self.segments: List[Seg] = list(segments)
        self.total_ms = sum(s.ms for s in self.segments)

    @classmethod
    def from_config(cls, cfg: Sequence[dict]) -> "Channel":
        """Build from plain dicts, e.g.
        Channel.from_config([{'ms':2000,'snr_db':35},
                             {'ms':3000,'snr_db':35,'snr_end':5,'collision':0.1}])"""
        return cls([Seg(**d) for d in cfg])

    def state(self, t_ms: float) -> ChannelState:
        """Channel state at time t (ms)."""
        t = max(0.0, min(t_ms, self.total_ms - 1e-9))
        acc = 0.0
        for s in self.segments:
            if t < acc + s.ms:
                frac = (t - acc) / s.ms if s.ms else 0.0
                v = s.snr_db if s.snr_end is None else s.snr_db + (s.snr_end - s.snr_db) * frac
                return ChannelState(max(SNR_MIN, min(SNR_MAX, v)), s.collision, s.delay_spread_us, s.obss,
                                    s.mimo_db, s.lgi_db, s.quiet, s.quiet_gap_ms)
            acc += s.ms
        s = self.segments[-1]
        return ChannelState(s.snr_end if s.snr_end is not None else s.snr_db,
                            s.collision, s.delay_spread_us, s.obss, s.mimo_db, s.lgi_db, s.quiet, s.quiet_gap_ms)
