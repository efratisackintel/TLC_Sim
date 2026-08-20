"""Offline builder: extract canonical PER-vs-SNR curves from the PERModel .fig set
into a compact LUT (tlcsim/data/per_lut.npz) that fully drives B2.

Canonical selection per (bw, mcs, nss, gi08):
  * PER.*.fig only, DisplayName prefix "PER:" (excludes DPER/HPER)
  * SU full-band RU (RUsize = max in fig), RUindex 1, PPM 0 (AWGN/LDPC are the
    only values present)
  * antenna: nss1 -> 1x1, nss2 -> 2x2
  * GI/LTF: gi08 -> (0.8 us, 2xLTF); not gi08 -> (3.2 us, 4xLTF)
Stores each curve's sorted SNR (dB) + PER, plus the sensitivity SNR and its PER
target parsed from the "SNR_10^-k = <dB>" annotation.

Run from the PERModel folder:
    python build_per_lut.py
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np

from fig_to_xlsx import extract_curves, clean_name, parse_config

FIG_DIR = "WiFi_EHT_Extended_HVT/WiFi_EHT_Extended_HVT"
OUT = "../tlcsim/data/per_lut.npz"

# gi08 -> (GI us, LTF); nss -> antenna (SISO uses 1x2 = 2-RX diversity, MIMO uses 2x2)
GI_LTF = {True: (0.8, 2), False: (3.2, 4)}
NSS_ANT = {1: "1x2", 2: "2x2"}


def _snr_sens(cleaned: str):
    """Parse 'SNR_10^-k = <dB>' -> (snr_db, per_target)."""
    m = re.search(r"SNR_10\^(-?\d+)\s*=\s*(-?[\d.]+)", cleaned)
    if not m:
        return None, None
    return float(m.group(2)), 10.0 ** int(m.group(1))


def _bw_mcs(path: str):
    m = re.search(r"FBW(\d+)\.MCS(\d+)", os.path.basename(path))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build():
    figs = sorted(glob.glob(f"{FIG_DIR}/PER.*.fig"))
    print(f"Scanning {len(figs)} PER figs...")

    keys, xs, ys, snr_sens, per_tgt = [], [], [], [], []
    for path in figs:
        bw, mcs = _bw_mcs(path)
        if bw is None:
            continue
        curves = extract_curves(path)
        parsed = []
        for c in curves:
            n = clean_name(c["name"])
            if not n.startswith("PER:"):
                continue
            parsed.append((c, parse_config(n), n))
        ru_max = max((cfg["RUsize"] for _, cfg, _ in parsed if cfg["RUsize"]),
                     default=None)

        for nss, ant in NSS_ANT.items():
            for gi08, (gi, ltf) in GI_LTF.items():
                sel = [(c, n) for c, cfg, n in parsed
                       if cfg["PPM"] == 0 and cfg["RUsize"] == ru_max
                       and cfg["RUindex"] == 1 and cfg["Antenna"] == ant
                       and cfg["GI [us]"] == gi and cfg["LTF"] == ltf]
                if not sel:
                    continue
                # duplicates are identical; take the longest sweep, tie -> first
                c, n = max(sel, key=lambda t: t[0]["x"].size)
                order = np.argsort(c["x"])
                x = c["x"][order].astype(np.float32)
                y = np.clip(c["y"][order], 0.0, 1.0).astype(np.float32)
                s, tgt = _snr_sens(n)
                keys.append(f"{bw},{mcs},{nss},{int(gi08)}")
                xs.append(x)
                ys.append(y)
                snr_sens.append(np.float32(s if s is not None else np.nan))
                per_tgt.append(np.float32(tgt if tgt is not None else np.nan))
        print(f"  {os.path.basename(path)} -> total keys now {len(keys)}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {"keys": np.array(keys),
               "snr_sens": np.array(snr_sens, dtype=np.float32),
               "per_target": np.array(per_tgt, dtype=np.float32)}
    for i, (x, y) in enumerate(zip(xs, ys)):
        payload[f"x{i}"] = x
        payload[f"y{i}"] = y
    np.savez_compressed(OUT, **payload)
    size = os.path.getsize(OUT) / 1024
    print(f"Saved {OUT}: {len(keys)} curves, {size:.1f} KB")


if __name__ == "__main__":
    build()
