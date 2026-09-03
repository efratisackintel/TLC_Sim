"""Shared rate definitions and PHY tables (data used by B2 and B4)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List

# Firmware expected-throughput tables, taken verbatim from fw rateScaleMng.c `expectedTptHe`
# (stored as Mbps x10). Indexed [BW]['08'|'32' (GI 0.8/3.2us)][NSS 1|2] -> MCS 0..13.
EXP_TPT_HE = {
    20: {'32': {1: [62, 124, 186, 248, 372, 497, 559, 621, 745, 828, 932, 1035, 1060, 1170],
                2: [124, 248, 372, 497, 745, 994, 1118, 1243, 1491, 1657, 1864, 2071, 2030, 2350]},
         '08': {1: [73, 146, 219, 292, 438, 585, 658, 731, 877, 975, 1096, 1218, 1230, 1360],
                2: [146, 292, 438, 585, 877, 1170, 1316, 1462, 1755, 1950, 2193, 2437, 2480, 2750]}},
    40: {'32': {1: [124, 248, 372, 497, 745, 994, 1118, 1243, 1491, 1657, 1864, 2071, 2230, 2460],
                2: [248, 497, 745, 994, 1491, 1989, 2237, 2486, 2983, 3315, 3729, 4143, 4270, 4950]},
         '08': {1: [146, 292, 438, 585, 877, 1170, 1316, 1462, 1755, 1950, 2193, 2437, 2600, 2870],
                2: [292, 585, 877, 1170, 1755, 2340, 2632, 2925, 3510, 3900, 4387, 4875, 5230, 5780]}},
    80: {'32': {1: [260, 520, 780, 1041, 1561, 2082, 2342, 2603, 3123, 3470, 3904, 4338, 4690, 5180],
                2: [520, 1041, 1561, 2082, 3123, 4165, 4685, 5206, 6247, 6941, 7809, 8677, 9000, 10430]},
         '08': {1: [306, 612, 918, 1225, 1837, 2450, 2756, 3062, 3675, 4083, 4593, 5104, 5470, 6040],
                2: [612, 1225, 1837, 2450, 3675, 4900, 5512, 6125, 7350, 8166, 9187, 10208, 11010, 12170]}},
    160: {'32': {1: [520, 1041, 1561, 2082, 3123, 4165, 4685, 5206, 6247, 6941, 7809, 8677, 9870, 10900],
                 2: [1041, 2082, 3123, 4165, 6247, 8330, 9371, 10412, 12495, 13883, 15618, 17354, 18940, 21960]},
          '08': {1: [612, 1225, 1837, 2450, 3675, 4900, 5512, 6125, 7350, 8166, 9187, 10208, 11520, 12720],
                 2: [1225, 2450, 3675, 4900, 7350, 9800, 11025, 12250, 14700, 16333, 18375, 20416, 23179, 25630]}},
    320: {'32': {1: [1140, 2260, 3380, 5260, 6660, 8810, 9870, 10900, 12960, 14320, 15990, 17630, 18940, 19320],
                 2: [2180, 4250, 6660, 8810, 12960, 16980, 18940, 21960, 26110, 28800, 32190, 35430, 38080, 43380]},
          '08': {1: [1340, 2660, 3970, 5260, 7800, 10300, 11520, 12720, 15110, 16670, 18600, 21260, 23170, 25630],
                 2: [2570, 4930, 7800, 10300, 15110, 20720, 23170, 25630, 30430, 33540, 37200, 42520, 45720, 50400]}},
}
# 80 MHz / SISO / 0.8us slice (Mbps) - retained for MCS count/labels
BASE_TPT = [v / 10 for v in EXP_TPT_HE[80]['08'][1]]
MOD = ["BPSK 1/2", "QPSK 1/2", "QPSK 3/4", "16QAM 1/2", "16QAM 3/4", "64QAM 2/3",
       "64QAM 3/4", "64QAM 5/6", "256QAM 3/4", "256QAM 5/6", "1024QAM 3/4",
       "1024QAM 5/6", "4096QAM 3/4", "4096QAM 5/6"]
BW_FACTOR = {20: 0.25, 40: 0.5, 80: 1.0, 160: 2.0, 320: 4.0}   # retained only to enumerate bandwidths
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
    """Effective throughput (Mbps) from the firmware expectedTptHe table."""
    t = EXP_TPT_HE.get(r.bw)
    if not t:
        return 0.0
    arr = t['08' if r.gi08 else '32'][2 if r.nss >= 2 else 1]
    return arr[r.mcs] / 10 if 0 <= r.mcs < len(arr) else 0.0


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
