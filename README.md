# TLC_Sim — WiFi Firmware TLC (Rate‑Scale) Simulation

## TLC Expert Agent

This workspace includes a read-only VS Code **TLC Expert** agent for analyzing
Rate Scale Manager behavior, firmware-versus-simulator differences, PER/SR
curves, and TVA results. See [TLC Expert Usage](../Agents/TLC%20Expert%20Usage.md)
for prompt examples and analysis hints.

A small, self‑contained Python simulation of the WiFi firmware **Transmit‑Link‑Control (TLC / rate‑scaling)** algorithm, plus a **data‑driven PER model** built from measured EHT PER‑vs‑SNR curves and interactive teaching docs.

The rate picker is chosen to maximize **effective throughput = peak_rate × Success‑Ratio**, exactly like the real Rate‑Scale Manager, and the PER model that feeds it comes entirely from measured firmware curves (no analytic sigmoid).

## ▶ Open the interactive docs

[![Open Playground](https://img.shields.io/badge/%E2%96%B6%20Open-Playground-0071C5?style=for-the-badge&logo=googlechrome&logoColor=white)](https://efratisackintel.github.io/TLC_Sim/doc/tlc_playground.html)
&nbsp;
[![Open Architecture](https://img.shields.io/badge/%E2%96%B6%20Open-Interactive%20Architecture-2E8B57?style=for-the-badge&logo=googlechrome&logoColor=white)](https://efratisackintel.github.io/TLC_Sim/doc/tlc_playground.html#doc)
&nbsp;
[![Open PER Explorer](https://img.shields.io/badge/%E2%96%B6%20Open-PER%20Model%20Explorer-7C3AED?style=for-the-badge&logo=googlechrome&logoColor=white)](https://efratisackintel.github.io/TLC_Sim/doc/per_model_explorer.html)

> The buttons open the **live** interactive pages on **GitHub Pages**. Enable it once (one‑time toggle): repo **Settings → Pages → Build and deployment → Source: _Deploy from a branch_ → Branch: `main` / `/ (root)` → Save**. After ~1 minute the site is live at `https://efratisackintel.github.io/TLC_Sim/` and rebuilds automatically on every push. (Opening the `.html` files directly on github.com only shows source, not the live page.)

**What each one is:**
- **▶ Playground** ([doc/tlc_playground.html](doc/tlc_playground.html)) — three tabs: **Live decision** (set the channel SNR and watch TLC pick MCS / streams / bandwidth / GI; all‑MCS PER‑vs‑SNR chart, fixed‑total‑power (PSD) penalty toggle, Mbps axis; Max BW defaults to **320 MHz**, MIMO), **Simulation** (closed‑loop scenario over time — throughput / MCS / BW / streams charts, numbered SEARCH bands, search‑cycle log, KPIs incl. *time between SC* and *SC duration*), and **Architecture** (the interactive block diagram embedded).
- **▶ Interactive architecture** ([doc/tlc_playground.html#doc](doc/tlc_playground.html#doc)) — click blocks B1–B6 for I/O and flow diagrams; the integrated **PER Model Explorer** lives under **B2** (tabs for frame BW · channel BW · antenna · GI). Standalone copy kept at `doc/tlc_sim_architecture.html`.
- **▶ PER Model Explorer** ([doc/per_model_explorer.html](doc/per_model_explorer.html)) — every measured PER curve, per permutation, with a log‑axis toggle and CSV export.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install numpy scipy matplotlib openpyxl

python run_example.py        # run a scenario, print KPIs, write tlc_run.csv
python gui.py                # Tkinter GUI to run scenarios and plot
```

## Simulation package (`tlcsim/`)

| Block | File | Role |
|---|---|---|
| B1 | `channel.py` | Time‑varying channel (SNR dB + collision) |
| B2 | `per_model.py` | **Data‑driven** PER = f(rate, SNR) from measured curves |
| B3 | `emulator.py` | Rate table + channel → TX statistics (Success Ratio) |
| B4 | `tlc.py` | The rate picker under test (`ReferenceTLC`) |
| B5 | `results.py` | Run log + KPIs (CSV, summary) |
| B6 | `harness.py` | Closed loop + simulated clock + scenario runner |

B2 loads its curves from `tlcsim/data/per_lut.npz` (canonical full‑band SISO/MIMO subset).

## PER model data (`PERModel/`)

Tools to extract the measured EHT PER curves from the MATLAB `.fig` set into a compact catalog and a human‑readable workbook:

- `build_per_lut.py` → `tlcsim/data/per_lut.npz` (the B2 operational LUT)
- `build_per_catalog.py` → `PERModel/per_catalog.npz` (all 135 permutations: frame BW × channel BW × antenna × GI)
- `build_per_workbook.py` → `PERModel/PER_Model_AllPermutations.xlsx` (wide Sensitivity & Throughput sheets + per‑case log‑Y PER charts)
- `fig_viewer.py`, `fig_to_xlsx.py` — parse/plot/export individual `.fig` files

> The raw `.fig` dataset (`PERModel/WiFi_EHT_Extended_HVT/`, ~135 MB) is **not** committed — regenerate the catalog from a local copy if needed.

## TVA sim‑vs‑lab workbooks (`Results/`)

Per‑bandwidth **TVA** (Throughput‑vs‑Attenuation) comparison of the simulated TLC against genie‑best and real lab logs, one `.xlsx` per BW.

```powershell
python PERModel\build_tva_compare.py    # → Results/tva_sim_vs_lab_{20,40,80,160,320}mhz.xlsx
```

- Generator: [PERModel/build_tva_compare.py](PERModel/build_tva_compare.py) — Python port of the playground TLC; sweeps SNR 44 → 2 dB, aggregates per step, auto‑aligns RSSI↔SNR, and matches lab summaries from `PERModel/RefTVA/*.json`.
- Each workbook has a **TVA** sheet (sim / genie / lab columns, colour‑coded), a **Charts** sheet, and an **RSSI‑to‑SNR** sheet (live Excel formulas: Noise Floor, Estimated RSSI, RSSI‑to‑SNR Diff).

## Notes

- The PER model is **Success‑Ratio driven** (measured PER → SR), not SNR‑driven; RSSI is only a fallback.
- The playground's PSD penalty models fixed total TX power (≈ 3 dB less per subcarrier per bandwidth doubling), which makes the chosen bandwidth adapt with SNR.

## Lessons learned — keeping the sim FW‑faithful

Insights from aligning the simulated TLC to the real Rate‑Scale Manager (see **§8 · TLC flow** in the architecture doc). The sim tracks genie within ~99% and the lab logs across all bandwidths.

- **Search fallback must be the last *known‑good* rate, not the current one.** Seeding a search cycle from the rate you just downscaled *from* (after a failure) makes the cycle "settle" back onto a dead rate. On a **PER cliff** (e.g. 20 MHz SNR 20: MCS7 = 100% SR, MCS8 = 0%) every probe reads 0, so nothing beats the failed seed and the sim commits a full 2000‑frame dwell (~300 ms) at 0% SR. Fall back to the last MCS that met the 90% hold threshold — this is what RS_MNG does.
- **Detect a failing rate fast; don't burn the whole optimal window.** A 2000‑frame ("optimal") dwell only applies while the rate *works*. If SR collapses below the force‑down threshold, abort within a few frames — the FW reacts within a few BlockAck stat updates, not 2000 frames. A stale known‑good MCS can still leak across an SNR step, so this fast‑fail is the safety net.
- **Match the FW's guard timers.** Upscale throttle ≈ **200 ms** (`RS_MNG_UPSCALE_MAX_FREQUENCY`) and avoid‑higher‑MCS cooldown ≈ **1 s** after a collapse. Too‑short guards make the sim re‑poke a failed rate every few frames and oscillate.
- **Don't over‑clamp the warm start.** Seeding the initial MCS from RSSI/SNR (no artificial MCS≤3 cap) removes a spurious climb artifact at the top of each sweep; `_rsMngSetInitRate` seeds proportional to signal.
- **Genie is an idealized upper bound; the lab averages over seconds.** Per‑step 1‑second sim windows expose transient mistakes that a ~7 s lab measurement averages out — so residual gaps at the very low‑SNR tail (near the noise floor) are expected, not bugs.
- **Validate against instrumented per‑window traces, not intuition.** The 20 MHz gap looked like "search overhead"; a per‑window trace proved search was only ~3% of airtime and the real cause was one 300 ms dead dwell. Always confirm the mechanism before "fixing" it.

