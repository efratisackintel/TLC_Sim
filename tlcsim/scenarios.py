"""Ready-made scenarios + easy config helpers for the simulation user.

Each returns a Channel. Mix and match, or build your own with Channel([Seg(...), ...]).
"""
from __future__ import annotations
from .channel import Channel, Seg


def steady(snr_db: float = 32, collision: float = 0.05, ms: float = 6000) -> Channel:
    """Constant, healthy link."""
    return Channel([Seg(ms, snr_db, collision=collision)])


def fade_and_recover(good: float = 40, bad: float = 6, seg_ms: float = 3000) -> Channel:
    """Good link, gradual fade down, then gradual recovery (ramps)."""
    return Channel([Seg(seg_ms, good),
                    Seg(seg_ms, good, bad),      # ramp down
                    Seg(seg_ms, bad, good)])     # ramp up


def sudden_drop(good: float = 40, bad: float = 8, ms: float = 3000) -> Channel:
    """Sudden step down, then step back up (tests reaction time)."""
    return Channel([Seg(ms, good), Seg(ms, bad), Seg(ms, good)])


def interference_burst(snr_db: float = 35, burst_collision: float = 0.4,
                       ms: float = 2000) -> Channel:
    """Steady SNR with a middle burst of collisions/interference."""
    return Channel([Seg(ms, snr_db, collision=0.02),
                    Seg(ms, snr_db, collision=burst_collision),
                    Seg(ms, snr_db, collision=0.02)])


SCENARIOS = {
    "steady": steady,
    "fade_and_recover": fade_and_recover,
    "sudden_drop": sudden_drop,
    "interference_burst": interference_burst,
}
