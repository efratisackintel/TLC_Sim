# TLC_Sim — WiFi Firmware TLC (Rate‑Scale) Simulation

A small, self‑contained Python simulation of the WiFi firmware **Transmit‑Link‑Control (TLC / rate‑scaling)** algorithm, plus a **data‑driven PER model** built from measured EHT PER‑vs‑SNR curves and interactive teaching docs.

The rate picker is chosen to maximize **effective throughput = peak_rate × Success‑Ratio**, exactly like the real Rate‑Scale Manager, and the PER model that feeds it comes entirely from measured firmware curves (no analytic sigmoid).

## Interactive docs (open the HTML files in a browser)

> These are standalone HTML. Clone the repo and open them locally, or enable **GitHub Pages** (Settings → Pages → deploy from `main`/`root`) to view them live at `https://efratisackintel.github.io/TLC_Sim/doc/<file>.html`.

- **Playground** — [`doc/tlc_playground.html`](doc/tlc_playground.html): set the channel SNR and watch TLC pick MCS / streams / bandwidth / GI. Includes the all‑MCS PER‑vs‑SNR chart, a fixed‑total‑power (PSD) penalty toggle, and an effective‑throughput (Mbps) axis.
- **Interactive architecture** — [`doc/tlc_sim_architecture.html`](doc/tlc_sim_architecture.html): click blocks B1–B6 for inputs/outputs, flow diagrams, and (under **B2**) the integrated **PER Model Explorer** (tabs for frame BW · channel BW · antenna · GI).
- **PER Model Explorer (standalone)** — [`doc/per_model_explorer.html`](doc/per_model_explorer.html): every measured PER curve, per permutation, with a log‑axis toggle and CSV export.

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

## Notes

- The PER model is **Success‑Ratio driven** (measured PER → SR), not SNR‑driven; RSSI is only a fallback.
- The playground's PSD penalty models fixed total TX power (≈ 3 dB less per subcarrier per bandwidth doubling), which makes the chosen bandwidth adapt with SNR.
