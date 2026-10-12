"""Extract the FULL Channel-D (with beamforming) PER catalog into per_catalog_chd.npz.

Source: the "channel D with BF per model" .fig set (WiFi PeP, 09Sep2024 capture),
which sweeps the PHY formats present (EHT/HE/VHT), each under its own
Figure/WiFi_<FMT>_SU_BF/ folder. Unlike the AWGN set this is IEEE channel D
(multipath) with beamforming, so the operating point carries extra dimensions:

  format x frameBW (fig FBW) x channelBW x antenna (e.g. 4x2 = BF) x Nss
        x GI x LTF x Control (LOW/HIGH x {2,4,8}) x MCS

Canonical per curve: PER-prefixed line (excludes DPER/HPER), PPM 0, RUindex 1;
duplicate length sweeps collapsed to the longest (tie -> first). No AWGN mixing:
this catalog is Channel-D only and lives alongside the AWGN per_catalog.npz.

Stores each curve's sorted SNR + PER, plus the sensitivity SNR (SNR at 10% PER)
and target parsed from the "SNR_10^-k = <dB>" annotation.

Run from repo root:
    python PERModel/build_per_catalog_chd.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, "PERModel")
from fig_to_xlsx import extract_curves, clean_name, parse_config

FIG_ROOT = ("PERModel/channel D with BF per model/OneDrive_2026-09-14/SU BF/"
            "WiFi_PeP_SU_09Sep2024_173335.Results/Figure")
OUT = "PERModel/per_catalog_chd.npz"
SNR_MIN, SNR_MAX = -5.0, 45.0                 # match the AWGN PER model's SNR window


def _snr_sens(cleaned: str):
    m = re.search(r"SNR_10\^(-?\d+)\s*=\s*(-?[\d.]+)", cleaned)
    if not m:
        return None, None
    return float(m.group(2)), 10.0 ** int(m.group(1))


def _gi_ltf(cfg: dict, cleaned: str):
    """(GI us, LTF) handling both HE/EHT 'CP & LTF x.x & x N' and VHT/HT 'GI n'."""
    gi, ltf = cfg["GI [us]"], cfg["LTF"]
    if gi is not None:                       # HE/EHT/UHR carry an explicit LTF
        return gi, (ltf if ltf is not None else "na")
    m = re.search(r"\bGI\s+(\d+)", cleaned)  # VHT/HT: 0 = NGI 0.8us, 1 = SGI 0.4us
    if m:
        return (0.4 if int(m.group(1)) == 1 else 0.8), "na"
    return None, None


def _fmt(folder: str):
    m = re.match(r"WiFi_(.+)_SU_BF$", os.path.basename(folder))
    return m.group(1) if m else None


def _fbw_mcs(path: str):
    m = re.search(r"FBW(\d+)\.MCS(\d+)", os.path.basename(path))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build():
    folders = sorted(glob.glob(f"{FIG_ROOT}/WiFi_*_SU_BF"))
    best = {}  # key -> (npoints, x, y, sens, tgt)
    total_figs = 0

    for folder in folders:
        fmt = _fmt(folder)
        if fmt is None:
            continue
        figs = sorted(glob.glob(f"{folder}/PER.*.fig"))
        total_figs += len(figs)
        print(f"{fmt}: scanning {len(figs)} PER figs...")
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
                ant, nss, chbw = cfg["Antenna"], cfg["Nss"], cfg["ChannelBW"]
                ctrl = cfg["Control"]
                gi, ltf = _gi_ltf(cfg, n)
                if None in (ant, nss, gi, ltf, ctrl, chbw):
                    continue
                key = f"{fmt},{fbw},{chbw},{ant},{nss},{gi},{ltf},{ctrl},{mcs}"
                x = c["x"]
                prev = best.get(key)
                if prev is None or x.size > prev[0]:
                    order = np.argsort(x)
                    xs = c["x"][order].astype(np.float32)
                    ys = np.clip(c["y"][order], 0, 1).astype(np.float32)
                    win = (xs >= SNR_MIN) & (xs <= SNR_MAX)
                    xs, ys = xs[win], ys[win]
                    s, tgt = _snr_sens(n)
                    best[key] = (x.size, xs, ys,
                                 np.float32(s if s is not None else np.nan),
                                 np.float32(tgt if tgt is not None else np.nan))
        print(f"  {fmt}: total keys now {len(best)}")

    keys = list(best.keys())
    payload = {"keys": np.array(keys),
               "snr_sens": np.array([best[k][3] for k in keys], dtype=np.float32),
               "per_target": np.array([best[k][4] for k in keys], dtype=np.float32)}
    for i, k in enumerate(keys):
        payload[f"x{i}"] = best[k][1]
        payload[f"y{i}"] = best[k][2]
    np.savez_compressed(OUT, **payload)
    print(f"Scanned {total_figs} PER figs across {len(folders)} formats.")
    print(f"Saved {OUT}: {len(keys)} curves, {os.path.getsize(OUT)/1024:.1f} KB")


if __name__ == "__main__":
    build()
