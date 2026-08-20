"""Extract the FULL PER catalog from the PERModel .fig set into per_catalog.npz.

Covers every measured permutation:
  frameBW (fig FBW)  x  channelBW (>= frameBW)  x  antenna (1x1/1x2/2x2)  x  GI (0.8/1.6/3.2)  x  MCS.
Canonical per curve: PER-prefixed line, PPM 0, RUindex 1, SU (AWGN, LDPC); duplicates
(length variants) collapsed to the longest sweep.

Stores each curve's sorted SNR + PER, plus the sensitivity SNR (SNR at 10% PER) and target.

Run from repo root:
    python PERModel/build_per_catalog.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, "PERModel")
from fig_to_xlsx import extract_curves, clean_name, parse_config

FIG_DIR = "PERModel/WiFi_EHT_Extended_HVT/WiFi_EHT_Extended_HVT"
OUT = "PERModel/per_catalog.npz"


def _snr_sens(cleaned: str):
    m = re.search(r"SNR_10\^(-?\d+)\s*=\s*(-?[\d.]+)", cleaned)
    if not m:
        return None, None
    return float(m.group(2)), 10.0 ** int(m.group(1))


def _fbw_mcs(path):
    m = re.search(r"FBW(\d+)\.MCS(\d+)", os.path.basename(path))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build():
    figs = sorted(glob.glob(f"{FIG_DIR}/PER.*.fig"))
    print(f"Scanning {len(figs)} PER figs...")
    best = {}  # key -> (npoints, x, y, sens, tgt)

    for path in figs:
        fbw, mcs = _fbw_mcs(path)
        if fbw is None:
            continue
        for c in extract_curves(path):
            n = clean_name(c["name"])
            if not n.startswith("PER:"):
                continue
            cfg = parse_config(n)
            if cfg["PPM"] != 0 or cfg["RUindex"] != 1:
                continue
            ant, gi, chbw = cfg["Antenna"], cfg["GI [us]"], cfg["ChannelBW"]
            if ant is None or gi is None or chbw is None:
                continue
            key = f"{fbw},{chbw},{ant},{gi},{mcs}"
            x = c["x"]; prev = best.get(key)
            if prev is None or x.size > prev[0]:
                order = np.argsort(x)
                s, tgt = _snr_sens(n)
                best[key] = (x.size, c["x"][order].astype(np.float32),
                             np.clip(c["y"][order], 0, 1).astype(np.float32),
                             np.float32(s if s is not None else np.nan),
                             np.float32(tgt if tgt is not None else np.nan))
        print(f"  {os.path.basename(path)} -> {len(best)} keys")

    keys = list(best.keys())
    payload = {"keys": np.array(keys),
               "snr_sens": np.array([best[k][3] for k in keys], dtype=np.float32),
               "per_target": np.array([best[k][4] for k in keys], dtype=np.float32)}
    for i, k in enumerate(keys):
        payload[f"x{i}"] = best[k][1]
        payload[f"y{i}"] = best[k][2]
    np.savez_compressed(OUT, **payload)
    print(f"Saved {OUT}: {len(keys)} curves, {os.path.getsize(OUT)/1024:.1f} KB")


if __name__ == "__main__":
    build()
