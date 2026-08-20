"""B3 — TX / Statistics Emulator (LMAC + PHY surrogate).

Applies the TLC's rate table against the PER model over a window of frames and returns
aggregated statistics (txed/acked -> Success Ratio). Coarse model: the TLC scales on the
primary rate's success ratio, so we report first-attempt txed/acked of the primary rate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import random
from .rates import Rate
from .channel import ChannelState
from .per_model import per


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
