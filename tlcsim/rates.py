"""Shared rate definitions and PHY tables (data used by B2 and B4)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List

# Effective throughput (Mbps): HE/EHT, 80 MHz, SISO, GI 0.8us, MCS 0..13
BASE_TPT = [30.6, 61.2, 91.8, 122.5, 183.7, 245, 275.6, 306.2,
            367.5, 408.3, 459.3, 510.4, 547, 604]
MOD = ["BPSK 1/2", "QPSK 1/2", "QPSK 3/4", "16QAM 1/2", "16QAM 3/4", "64QAM 2/3",
       "64QAM 3/4", "64QAM 5/6", "256QAM 3/4", "256QAM 5/6", "1024QAM 3/4",
       "1024QAM 5/6", "4096QAM 3/4", "4096QAM 5/6"]
BW_FACTOR = {20: 0.25, 40: 0.5, 80: 1.0, 160: 2.0, 320: 4.0}
BW_PENALTY = {20: 0, 40: 1, 80: 3, 160: 5, 320: 7}
NSS_PENALTY = 5
GI08, GI32 = 1.0, 0.85
MAX_MCS = len(BASE_TPT) - 1
BANDWIDTHS = [20, 40, 80, 160, 320]


@dataclass(frozen=True)
class Rate:
    """One PHY rate (the sim's simplified rate_n_flags)."""
    mcs: int
    nss: int = 1        # 1 = SISO, 2 = MIMO
    bw: int = 80        # MHz
    gi08: bool = True   # True = 0.8us GI, False = 3.2us GI

    def __str__(self) -> str:
        return f"MCS{self.mcs}·{'MIMO' if self.nss == 2 else 'SISO'}·{self.bw}MHz·{'0.8' if self.gi08 else '3.2'}us"


def expected_tpt(r: Rate) -> float:
    """Ideal effective throughput (Mbps) for a rate."""
    return BASE_TPT[r.mcs] * BW_FACTOR[r.bw] * (2 if r.nss == 2 else 1) * (GI08 if r.gi08 else GI32)


def sens_snr(r: Rate):
    """Measured sensitivity SNR (dB) for this rate, from the PER LUT (or None)."""
    from .per_model import sens_snr as _s
    return _s(r)


def all_rates(max_bw: int = 160, max_nss: int = 2, max_mcs: int = MAX_MCS,
              gi08=None) -> List[Rate]:
    """Every rate that has a measured PER curve within the caps, sorted by throughput."""
    from .per_model import lut_keys
    rates = []
    for k in lut_keys():
        bw, mcs, nss, gi = (int(v) for v in k.split(","))
        if bw <= max_bw and nss <= max_nss and mcs <= max_mcs \
                and (gi08 is None or int(bool(gi08)) == gi):
            rates.append(Rate(mcs, nss, bw, bool(gi)))
    rates.sort(key=expected_tpt)
    return rates
