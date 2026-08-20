"""B1 — Channel Configuration: time-varying channel state (ground truth).

The channel is expressed in real **SNR (dB)** so it can drive the data-based PER model
directly. Build a Channel from a list of segments; a segment is a constant SNR, or a
linear ramp if `snr_end` is given.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Sequence

SNR_MIN, SNR_MAX = -20.0, 60.0


@dataclass
class ChannelState:
    snr_db: float     # link SNR in dB (higher = cleaner link)
    collision: float  # 0..1 (probability a TX is lost to collision/interference)


@dataclass
class Seg:
    """One scenario segment. Constant `snr_db`, or a linear ramp to `snr_end`."""
    ms: float
    snr_db: float
    snr_end: Optional[float] = None
    collision: float = 0.0


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
                return ChannelState(max(SNR_MIN, min(SNR_MAX, v)), s.collision)
            acc += s.ms
        s = self.segments[-1]
        return ChannelState(s.snr_end if s.snr_end is not None else s.snr_db, s.collision)
