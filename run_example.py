"""Example runner — edit the scenario below and run:  python run_example.py

This is the easy entry point for a simulation user. Change the scenario / config,
run, then inspect the printed KPIs and the CSV.
"""
from tlcsim import run_sim, scenarios, ReferenceTLC, TLCConfig, Channel, Seg

# ── configure your scenario here (easy) ──────────────────────────────────
scenario = scenarios.fade_and_recover(good=95, bad=20, seg_ms=3000)

# …or build your own (constant or ramping segments):
# scenario = Channel([
#     Seg(ms=2000, snr_db=40),                        # steady, good
#     Seg(ms=3000, snr_db=40, snr_end=6),             # ramp down
#     Seg(ms=3000, snr_db=6, snr_end=40),             # ramp back up
#     Seg(ms=2000, snr_db=40, collision=0.35),        # interference burst
# ])

config = TLCConfig(max_bw=160, max_nss=2)     # station capabilities
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_sim(scenario, ReferenceTLC(), config, monte_carlo=False)
    result.summary()
    result.to_csv("tlc_run.csv")
    print("wrote tlc_run.csv")
