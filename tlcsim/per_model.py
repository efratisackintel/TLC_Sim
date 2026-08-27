"""B2 — PER Model: PER = f(rate, channel), driven ENTIRELY by measured data.

The PER comes from real EHT PER-vs-SNR curves extracted from the PERModel .fig set into
tlcsim/data/per_lut.npz (see PERModel/build_per_lut.py). There is NO analytic/sigmoid
model: for a given rate we look up its canonical PER curve and interpolate at the channel
SNR. Outside a curve's swept range the value saturates to 1.0 (100% PER) below and 0.0
(0% PER) above. Collision is applied on top: PER = 1 - (1 - PER_phy)(1 - collision).

LUT key = "bw,mcs,nss,gi08"  (gi08: 1 = 0.8us short GI, 0 = 3.2us long GI).
"""
from __future__ import annotations
import math
import os
from typing import Dict, Optional, Tuple

import numpy as np

from .rates import Rate, expected_tpt
from .channel import ChannelState

_LUT_PATH = os.path.join(os.path.dirname(__file__), "data", "per_lut.npz")
_CURVES: Optional[Dict[str, Tuple[np.ndarray, np.ndarray]]] = None
_META: Optional[Dict[str, Tuple[float, float]]] = None   # key -> (snr_sens, per_target)

# --- Synthetic delay-spread (ISI) model -----------------------------------
# The measured PER curves are AWGN only (no multipath). To let channel length
# matter we layer a SYNTHETIC (non-empirical) inter-symbol-interference penalty:
# when the RMS delay spread tau exceeds the guard interval (GI), part of each
# symbol's energy leaks into the next one -> an SNR penalty plus an irreducible
# PER floor. No effect while the GI covers tau (tau <= GI).
ISI_SNR_PENALTY_DB = 6.0   # dB SNR shift per unit of excess ratio (tau/GI - 1)
ISI_FLOOR_MAX = 0.5        # max irreducible PER floor from ISI
ISI_FLOOR_SCALE = 1.0      # how fast the floor saturates with excess


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


def _gi_us(r: Rate) -> float:
    """Guard interval of a rate in microseconds (sim models 0.8 or 3.2 us)."""
    return 0.8 if r.gi08 else 3.2


def isi_penalty(gi_us: float, tau_us: float) -> Tuple[float, float]:
    """Synthetic (NON-empirical) delay-spread effect: returns (snr_penalty_db, per_floor).

    No effect while the guard interval covers the delay spread (tau <= GI). When
    tau > GI the excess ratio drives an SNR penalty and an irreducible PER floor."""
    if tau_us <= 0.0 or gi_us <= 0.0:
        return 0.0, 0.0
    excess = tau_us / gi_us - 1.0                # delay spread beyond the guard
    if excess <= 0.0:
        return 0.0, 0.0
    snr_pen = ISI_SNR_PENALTY_DB * excess
    floor = ISI_FLOOR_MAX * (1.0 - math.exp(-excess / ISI_FLOOR_SCALE))
    return snr_pen, floor


def per(rate: Rate, ch: ChannelState) -> float:
    """Probability a transmission at `rate` fails on channel `ch` (0..1). Data-driven
    AWGN PER + synthetic delay-spread ISI penalty + collision."""
    tau = getattr(ch, "delay_spread_us", 0.0)
    snr_pen, floor = isi_penalty(_gi_us(rate), tau) if tau > 0.0 else (0.0, 0.0)
    p = phy_per(rate, ch.snr_db - snr_pen)
    if floor > 0.0:
        p = max(p, floor)
    p_success = (1.0 - p) * (1.0 - ch.collision)
    return max(0.0, min(1.0, 1.0 - p_success))


def retry_chain(p: Rate, base: Rate = None):
    """Retry table (FW _rsMngBuildRatesTbl): entry 0 = the sent (test) rate; the fallback
    ladder is built from the STABLE column (`base`) — during a search cycle that is the
    pre-search committed rate, not the test column. For dwell/upscale base = primary."""
    b = base if base is not None else p
    chain = [p]                                            # entry 0 = sent (test) rate
    if b != p:
        chain.append(b)                                   # stable rate as first fallback (search)
    if b.mcs >= 1:
        chain.append(Rate(b.mcs - 1, b.nss, b.bw, b.gi08))
    if b.mcs >= 2:
        chain.append(Rate(b.mcs - 2, b.nss, b.bw, b.gi08))
    chain.append(Rate(0, 1, b.bw, False))     # robust: SISO, long GI
    chain.append(Rate(0, 1, 20, False))       # legacy-ish: 20 MHz, most robust
    return chain


def retry_tput(p: Rate, base: Rate, ch: ChannelState, frame_bits: float):
    """Airtime-based delivery through the retry chain: a failed primary is redelivered at a
    fallback rate, so throughput dips to ~the fallback rate (not zero).
    Returns (tput_mbps, airtime_s_per_frame, first_attempt_fail)."""
    reach, e_t, deliv, first_fail = 1.0, 0.0, 0.0, 0.0
    for k, r in enumerate(retry_chain(p, base)):
        fail = per(r, ch)
        phy = expected_tpt(r)
        t_r = frame_bits / (phy * 1e6) if phy > 0 else 1e6
        e_t += reach * t_r
        deliv += reach * (1.0 - fail)
        if k == 0:
            first_fail = fail
        reach *= fail
        if reach < 1e-4:
            break
    tput = (deliv * frame_bits) / e_t / 1e6 if e_t > 0 else 0.0
    return tput, e_t, first_fail
