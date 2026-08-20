"""B5 — run history / log + KPIs."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import csv


@dataclass
class Record:
    t_ms: float
    dt_ms: float
    rate: str
    mcs: int
    nss: int
    bw: int
    snr_db: float
    collision: float
    sr: float
    tpt: float        # achieved effective throughput (Mbps) = SR x expected_tpt(primary)
    best_tpt: float   # best achievable this window (over all rates)
    mode: str         # "search" / "dwell"  (short vs long window)
    state: str = "-"  # "STAY" / "SEARCH"   (the TLC state machine)


@dataclass
class RunResult:
    records: List[Record] = field(default_factory=list)

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_ms", "dt_ms", "rate", "mcs", "nss", "bw", "snr_db", "collision",
                        "sr", "tpt_mbps", "best_tpt_mbps", "mode", "state"])
            for r in self.records:
                w.writerow([f"{r.t_ms:.1f}", f"{r.dt_ms:.2f}", r.rate, r.mcs, r.nss, r.bw,
                            f"{r.snr_db:.1f}", f"{r.collision:.2f}", f"{r.sr:.3f}",
                            f"{r.tpt:.1f}", f"{r.best_tpt:.1f}", r.mode, r.state])

    def summary(self) -> dict:
        recs = self.records
        if not recs:
            return {}
        tot = sum(r.dt_ms for r in recs) or 1.0
        avg_sr = sum(r.sr * r.dt_ms for r in recs) / tot
        avg_tpt = sum(r.tpt * r.dt_ms for r in recs) / tot
        eff = sum((r.tpt / r.best_tpt if r.best_tpt > 0 else 0) * r.dt_ms for r in recs) / tot
        switches = sum(1 for a, b in zip(recs, recs[1:]) if a.rate != b.rate)
        dwell = sum(r.dt_ms for r in recs if r.mode == "dwell") / tot
        s = {"duration_ms": round(tot, 1), "windows": len(recs),
             "avg_SR": round(avg_sr, 3), "avg_tpt_mbps": round(avg_tpt, 1),
             "efficiency": round(eff, 3), "rate_switches": switches,
             "time_in_dwell": round(dwell, 3)}
        print("--- TLC run summary ---")
        for k, v in s.items():
            print(f"  {k:16}: {v}")
        print("-----------------------")
        return s
