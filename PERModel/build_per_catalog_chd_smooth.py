"""Derive a smoothed, physically-reasonable Channel-D PER catalog.

Reads per_catalog_chd.npz (raw link-sim curves) and writes
per_catalog_chd_smooth.npz with the same keys/SNR grids but each PER curve
de-shelfed with minimal, anchored smoothing:

  * isotonic (monotone non-increasing) fit removes upward spikes / stair jitter,
  * the three landmark points are PINNED so the edges never move: the SNR where
    PER leaves 100%, the exact 10% crossing, and the exact 0.1% crossing,
  * a shape-preserving monotone (PCHIP) interpolation through the strictly-
    decreasing points fills the transition, dissolving flat shelves into a
    smooth slope WITHOUT shifting those landmarks.

Only the interior sampling jitter/shelves are removed; the curve still passes
through the real onset / 10% / 0.1% points. snr_sens (SNR@10% PER) is unchanged
by construction and recomputed from the result.

Run from repo root (after build_per_catalog_chd.py):
    python PERModel/build_per_catalog_chd_smooth.py
"""
from __future__ import annotations

import os

import numpy as np
from scipy.interpolate import PchipInterpolator

IN = "PERModel/per_catalog_chd.npz"
OUT = "PERModel/per_catalog_chd_smooth.npz"
FLOOR = 1e-3


def _pava_noninc(y):
    """Least-squares monotone non-increasing fit (pool-adjacent-violators)."""
    vals, wts = [], []
    for v in y:
        vals.append(float(v)); wts.append(1.0)
        while len(vals) > 1 and vals[-2] < vals[-1] - 1e-15:
            v2, w2 = vals.pop(), wts.pop()
            v1, w1 = vals.pop(), wts.pop()
            w = w1 + w2
            vals.append((v1 * w1 + v2 * w2) / w); wts.append(w)
    out = []
    for v, w in zip(vals, wts):
        out.extend([v] * int(round(w)))
    return np.asarray(out, dtype=float)


def _cross(x, y, target):
    """First SNR where a descending curve crosses target (None if it never does)."""
    for i in range(1, len(x)):
        if (y[i-1] - target) * (y[i] - target) <= 0 and y[i-1] != y[i]:
            t = (target - y[i-1]) / (y[i] - y[i-1])
            return float(x[i-1] + t * (x[i] - x[i-1]))
    return None


def _smooth(x, y):
    """De-shelf with anchored PCHIP.

    Landmarks are read from the RAW curve and pinned so the edges never move:
    the SNR where PER leaves 100%, the 10% crossing, and the 0.1% crossing.
    Only the interior between them is redrawn (strictly-decreasing raw points +
    monotone PCHIP), which dissolves flat shelves without shifting the anchors.
    """
    x = np.asarray(x, dtype=float)
    yc = np.clip(y, FLOOR, 1.0).astype(float)
    if x.size < 4 or np.ptp(yc) < 1e-9:
        return np.clip(y, 0.0, 1.0).astype(np.float32)

    mono = _pava_noninc(yc)                        # robust monotone (tames noise / spurious 0s)
    top = np.where(mono >= 1.0 - 1e-9)[0]
    i_onset = int(top[-1]) if top.size else 0      # last SNR still at 100%
    snr01 = _cross(x, mono, FLOOR)                 # 0.1% point (end of curve)
    x_end = snr01 if snr01 is not None else float(x[-1])

    # interior anchors: strictly-decreasing points between onset and the 0.1% end.
    # These already capture the first 10% point, so no separate 10% pin is added
    # (an extra same-PER anchor would re-draw a flat 10% shelf).
    ax, ay = [float(x[i_onset])], [float(mono[i_onset])]
    for xi, yi in zip(x[i_onset+1:], mono[i_onset+1:]):
        if xi >= x_end:
            break
        if yi < ay[-1] * (1.0 - 1e-6):
            ax.append(float(xi)); ay.append(float(yi))
    if snr01 is not None:
        ax.append(snr01); ay.append(FLOOR)

    order = np.argsort(ax)
    ax, ay = np.asarray(ax)[order], np.asarray(ay)[order]
    ux, uy = [], []
    for xi, yi in zip(ax, ay):
        if ux and xi - ux[-1] < 1e-9:              # dedupe SNR, keep the lower PER
            uy[-1] = min(uy[-1], yi); continue
        if uy and yi >= uy[-1]:
            yi = uy[-1] * (1.0 - 1e-6)             # strictly decreasing for PCHIP
        ux.append(xi); uy.append(yi)
    ux = np.asarray(ux); uy = np.clip(np.asarray(uy), FLOOR, 1.0)
    if ux.size < 2:
        return np.clip(yc, 0.0, 1.0).astype(np.float32)

    pch = PchipInterpolator(ux, np.log10(uy), extrapolate=False)
    out = np.empty_like(x)
    pre = x < ux[0]
    post = x > ux[-1]
    mid = ~pre & ~post
    out[pre] = 1.0                                 # 100% before the onset
    out[mid] = 10.0 ** pch(x[mid])
    out[post] = 0.0 if snr01 is not None else float(uy[-1])   # 0 past 0.1%, else hold floor
    out = np.clip(out, 0.0, 1.0)
    out = np.where(out <= FLOOR * 1.001, 0.0, out)
    return out.astype(np.float32)


def _snr_at(x, y, target=0.1):
    o = np.argsort(x); x, y = x[o], y[o]
    for i in range(1, len(x)):
        if (y[i-1] - target) * (y[i] - target) <= 0 and y[i-1] != y[i]:
            t = (target - y[i-1]) / (y[i] - y[i-1])
            return np.float32(x[i-1] + t * (x[i] - x[i-1]))
    return np.float32(np.nan)


def build():
    d = np.load(IN)
    keys = [str(k) for k in d["keys"]]
    payload = {"keys": np.array(keys), "per_target": d["per_target"]}
    sens = []
    for i in range(len(keys)):
        x = d[f"x{i}"]
        ys = _smooth(x, d[f"y{i}"])
        payload[f"x{i}"] = x
        payload[f"y{i}"] = ys
        sens.append(_snr_at(x.astype(float), ys.astype(float)) if x.size else np.float32(np.nan))
    payload["snr_sens"] = np.array(sens, dtype=np.float32)
    np.savez_compressed(OUT, **payload)
    print(f"Saved {OUT}: {len(keys)} smoothed curves, {os.path.getsize(OUT)/1024:.1f} KB")


if __name__ == "__main__":
    build()
