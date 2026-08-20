"""B2 — PER Model: PER = f(rate, channel), driven ENTIRELY by measured data.

The PER comes from real EHT PER-vs-SNR curves extracted from the PERModel .fig set into
tlcsim/data/per_lut.npz (see PERModel/build_per_lut.py). There is NO analytic/sigmoid
model: for a given rate we look up its canonical PER curve and interpolate at the channel
SNR. Outside a curve's swept range the value saturates to 1.0 (100% PER) below and 0.0
(0% PER) above. Collision is applied on top: PER = 1 - (1 - PER_phy)(1 - collision).

LUT key = "bw,mcs,nss,gi08"  (gi08: 1 = 0.8us short GI, 0 = 3.2us long GI).
"""
from __future__ import annotations
import os
from typing import Dict, Optional, Tuple

import numpy as np

from .rates import Rate
from .channel import ChannelState

_LUT_PATH = os.path.join(os.path.dirname(__file__), "data", "per_lut.npz")
_CURVES: Optional[Dict[str, Tuple[np.ndarray, np.ndarray]]] = None
_META: Optional[Dict[str, Tuple[float, float]]] = None   # key -> (snr_sens, per_target)


def _load():
    global _CURVES, _META
    if _CURVES is not None:
        return
    if not os.path.exists(_LUT_PATH):
        raise FileNotFoundError(
            f"PER LUT not found at {_LUT_PATH}. Build it with PERModel/build_per_lut.py")
    d = np.load(_LUT_PATH, allow_pickle=False)
    keys = [str(k) for k in d["keys"]]
    _CURVES = {k: (d[f"x{i}"], d[f"y{i}"]) for i, k in enumerate(keys)}
    _META = {k: (float(d["snr_sens"][i]), float(d["per_target"][i]))
             for i, k in enumerate(keys)}


def _key(r: Rate) -> str:
    return f"{r.bw},{r.mcs},{r.nss},{1 if r.gi08 else 0}"


def lut_keys() -> set:
    _load()
    return set(_CURVES.keys())


def has_rate(r: Rate) -> bool:
    _load()
    return _key(r) in _CURVES


def sens_snr(r: Rate) -> Optional[float]:
    """SNR (dB) at the curve's PER target (sensitivity point), or None if unavailable."""
    _load()
    m = _META.get(_key(r))
    return m[0] if m and not np.isnan(m[0]) else None


def phy_per(r: Rate, snr_db: float) -> float:
    """PHY-only PER for a rate at a given SNR, from the measured curve (no collision)."""
    _load()
    entry = _CURVES.get(_key(r))
    if entry is None:
        return 1.0                               # no measured curve -> rate unusable
    x, y = entry
    return float(np.interp(snr_db, x, y, left=1.0, right=0.0))


def per(rate: Rate, ch: ChannelState) -> float:
    """Probability a transmission at `rate` fails on channel `ch` (0..1). Data-driven."""
    p = phy_per(rate, ch.snr_db)
    p_success = (1.0 - p) * (1.0 - ch.collision)
    return max(0.0, min(1.0, 1.0 - p_success))
