"""tlcsim — tiny closed-loop TLC (rate-scale) simulation.

Blocks (one file each):
  B1 channel.py     — Channel Configuration (time-varying ground truth, SNR dB)
  B2 per_model.py   — PER model: PER = f(rate, channel), driven by measured PER curves
  B3 emulator.py    — TX/Statistics emulator (LMAC+PHY surrogate)
  B4 tlc.py         — TLC rate picker (pluggable; ReferenceTLC provided)
  B5 results.py     — run history/log + KPIs
  B6 harness.py     — scheduler/clock + closed loop

Quick start:
    from tlcsim import run_sim, scenarios, ReferenceTLC
    res = run_sim(scenarios.fade_and_recover(), ReferenceTLC())
    res.summary(); res.to_csv("run.csv")
"""
from .rates import Rate, expected_tpt, sens_snr, all_rates
from .channel import Channel, Seg, ChannelState
from .per_model import per, phy_per, has_rate, lut_keys
from .emulator import simulate_window, WindowStats
from .tlc import TLC, ReferenceTLC, TLCConfig, LinkQuality
from .results import RunResult, Record
from .harness import run_sim
from . import scenarios

__all__ = ["run_sim", "scenarios", "Channel", "Seg", "ChannelState", "Rate",
           "ReferenceTLC", "TLC", "TLCConfig", "LinkQuality", "per", "phy_per",
           "has_rate", "lut_keys", "expected_tpt", "sens_snr", "all_rates",
           "simulate_window", "WindowStats", "RunResult", "Record"]
