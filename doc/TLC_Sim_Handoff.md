# TLC Simulation — Handoff & Lessons Notes

> Purpose: everything needed to **restart the conversation** without losing context.
> Scope: the `TLC_Sim` teaching/simulation project and the real firmware TLC facts it models.
> Last updated: 2026-08-19.

---

## 1. What this project is

A small, self-contained **Python simulation of the WiFi firmware Transmit-Link-Control (TLC / rate-scaling)** algorithm, plus **teaching material** (docs + interactive HTML) explaining how it works.

Two goals live side by side:
1. **Teach** how the firmware TLC picks rates (docs, PPTX, interactive HTML architecture page).
2. **Simulate / test** TLC logic in a fast closed loop so different rate-control algorithms can be compared.

Everything lives under:
```
c:\Users\eisack\OneDrive - Intel Corporation\Desktop\Efrat\TLC_Sim\
```

---

## 2. The single most important fact about TLC

**TLC is Success-Ratio (SR) driven, NOT SNR driven.**

- Inputs are per-rate **success/failure frame counts** → success ratio (SR), tracked with EWMA windows per (column, MCS).
- **RSSI is only a fallback** (used in `_rsMngHandleBeaconData` when there are no TX stats yet). SNR is *not* a TLC input.
- Outputs: **primary rate (PR)**, **bandwidth (BW)**, **guard interval (GI)**, **NSS**, and a **retry table** (primary + fallbacks + legacy).

---

## 3. Real firmware reference (source of truth)

Path (in the `wcd_fw-dev` workspace folder):
```
fw/src/umac/main/dataPath/rateScaleMng/
    rateScaleMng.c        <- main algorithm
    _rateScaleMng.h       <- constants
    rateScaleAggMng.c     <- aggregation manager
```

### 3.1 Search-cycle trigger — `_rsMngShouldStartSearchCycle` (rateScaleMng.c ~L4002)

**There is NO periodic/constant timer (no 500 ms tick) that starts a search cycle.**
The trigger is **frame-count driven**, with a time value used only as a *rate-limit guard*:

```
if (totalFramesSuccess > successFramesLimit):        # SUCCESS path
    if (previous cycle startReason was a FAIL):       # bypass guard to re-probe up fast
        start (reason = SUCCESS_FRAMES)
    elif (timeSinceLastSearch > 300 ms):              # rate-limit guard
        start (reason = SUCCESS_TIME)

if (totalFramesFailed > failedFramesLimit):          # FAIL path (checked after success)
    start (reason = FAIL_FRAMES)                      # immediate, NO time guard

else: return FALSE
```

- Failures react **immediately** (no timer) → find a surviving rate fast.
- Successes are **rate-limited** to ≥300 ms apart, *unless* the previous cycle was a FAIL.
- The perceived "period" is **emergent** (how fast counters overflow), never a fixed timer.

### 3.2 Key constants (`_rateScaleMng.h`)

| Constant | Value | Meaning |
|---|---|---|
| `RS_MNG_NON_LEGACY_SUCCESS_LIMIT` | 4500 | success frames → maybe upscale search |
| `RS_MNG_NON_LEGACY_FAILURE_LIMIT` | 400 | failed frames → immediate search |
| `RS_MNG_LEGACY_SUCCESS_LIMIT` | 480 | legacy-column success limit |
| `RS_MNG_LEGACY_FAILURE_LIMIT` | 160 | legacy-column failure limit |
| `RS_MNG_UPSCALE_SEARCH_CYCLE_MAX_FREQ` | 300 ms | min spacing between success-triggered searches |
| `RS_MNG_UPSCALE_MAX_FREQUENCY` | 200 ms | min spacing between in-column upscale *attempts* |
| `RS_MNG_UPSCALE_IGNORE_HIGHER_MCS` | 1000 ms | timeout to avoid a higher MCS that failed |
| `RS_MNG_OPTIMAL_RATE_FRAME_COUNT` | 2000 | optimal-rate window size |
| `RS_MNG_UPSCALE_AGG_FRAME_COUNT` | 20 | upscale aggregation frame count |
| `RS_MNG_PERFECT_SR` | 95 % | "perfect" success ratio |
| `RS_MNG_SR_NO_DECREASE` | 90 % | above this: don't downscale |
| `RS_MNG_SR_FORCE_DECREASE` | 15 % | below this: force downscale |
| `RS_MNG_IGNORE_HIGHER_MCS_THRESHOLD_SR` | 70 % | SR below which higher MCS is ignored |
| `RS_MNG_TIME_STAT_RESET_THRESHOLD` | 13 × 20 = 260 | stale-window guard: **invalidates stale TPT stats** (NOT a search trigger), rateScaleMng.c ~L3200 |

### 3.3 Other real-firmware behaviour NOT yet modelled in the sim
- TPC (transmit power control), AMSDU sizing, full aggregation manager.
- Full column graph (next-columns table, `MAX_NEXT_COLUMNS=8`, `MAX_COLUMN_CHECKS=4`).
- EWMA lookup tables and ms timers.
- 200 ms in-column upscale-attempt guard (separate from the 300 ms search guard).
- Legacy 480/160 limits when in a legacy column.
- The 10 s-ish stat-reset/flush behaviour.

---

## 4. The simulation package `tlcsim/` (6 blocks, one file per block)

Closed loop: **rate table → emulator → SR statistics → TLC decision → repeat**.
Pure stdlib; matplotlib only used by the GUI.

| Block | File | Role |
|---|---|---|
| B1 | `channel.py` | Time-varying channel (quality + collision). `Channel(segments)`, `.state(t_ms)`, `.from_config()`; `Seg{ms,quality,quality_end?,collision}` supports constant or linear ramp. |
| B2 | `per_model.py` | Pure `per(rate, ch, slope=0.16)`: `margin=quality-required_quality(rate)`; `p_link=sigmoid(margin*slope)`; `p_success=p_link*(1-collision)`; `PER=1-p_success`. |
| B3 | `emulator.py` | LMAC+PHY surrogate. `simulate_window(rate_table, ch, window_frames, monte_carlo, rng)` → `WindowStats{txed,acked,sr}`. Coarse `acked=round(N*(1-per))` or Monte-Carlo draws. |
| B4 | `tlc.py` | **The rate picker under test** (swap point). `ReferenceTLC` = column-based state machine. See §5. |
| B5 | `results.py` | `Record`, `RunResult.to_csv()`, `.summary()` (ASCII-safe KPIs). |
| B6 | `harness.py` | `run_sim(channel, tlc, config, frame_bytes, monte_carlo, seed, max_ms)` — closed loop + simulated clock. |

`rates.py` — `Rate{mcs,nss,bw,gi08}`; tables `BASE_TPT` (HE/EHT 80 MHz SISO 0.8µs MCS0-13 Mbps), `MCS_Q`, `BW_FACTOR`, `BW_PENALTY`, `NSS_PENALTY=5`, `GI08=1.0/GI32=0.85`, `BANDWIDTHS=[20,40,80,160,320]`; funcs `expected_tpt(r)`, `required_quality(r)`, `all_rates()`.

`scenarios.py` — `steady()`, `fade_and_recover(good=90,bad=20,seg_ms=3000)`, `sudden_drop()`, `interference_burst()`, `SCENARIOS` dict.

`__init__.py` — exports `run_sim`, `SCENARIOS`, `Channel`, `Seg`, `ReferenceTLC`, `TLC`, `TLCConfig`, `LinkQuality`, `per`, `expected_tpt`, etc.

`run_example.py` (repo root) — editable entry point; runs a scenario, prints summary, writes `tlc_run.csv`.

---

## 5. `ReferenceTLC` (B4) — current design

**A MODEL / swap-point, deliberately simplified — NOT a line-for-line copy of `rateScaleMng.c`.**

- Column = `(nss, bw, gi08)`. State: `col`, `mcs`, `sr{}` (EWMA per (col,mcs)), `state` ∈ {STAY, SEARCH}, `mode` ∈ {search, dwell}, `succ`/`fail` counters, `last_search_end_ms`, `last_reason`, `pending_reason`, `search_q`, `best`.
- Constants: `SR_PERFECT=0.95`, `SR_NO_DEC=0.90`, `SR_FORCE=0.15`, `THOLD_SEARCH=20`, `THOLD_DWELL=2000`, `EWMA_ALPHA=0.4`, `SUCCESS_LIMIT=4500`, `FAIL_LIMIT=400`, `SEARCH_TIME_GUARD_MS=300`.
- **STAY**: scale MCS (↑ if SR≥95%, ↓ if SR<90% or SR<15%, else hold).
- **Search trigger (faithful to firmware)**:
  ```
  reason = None
  if succ > 4500:
      if last_reason == "FAIL":          reason = "SUCCESS"   # bypass guard
      elif t - last_search_end > 300ms:  reason = "SUCCESS"
  if reason is None and fail > 400:      reason = "FAIL"       # no guard
  if reason: enter_search()
  ```
- **SEARCH**: score neighbour columns by `SR × expected_tpt`, keep best, settle back to STAY (set `last_reason=pending_reason`, `last_search_end_ms=t`).
- Helpers: `_rate()`, `_avgtpt()`, `_neighbours()` (toggle SISO/MIMO, ±BW step, toggle GI), `_retry_table()` (primary + 3 lower MCS + legacy `Rate(0,1,20,False)`), `_lq()`, `_enter_search(sr)`.

Validated: `fade_and_recover` 9 s → efficiency ~0.69–0.74, avg_tpt ~1268–1382 Mbps, climbs to MCS13·MIMO·160 on good channel, tracks fades; ~92 search cycles with the faithful trigger.

---

## 6. GUI — `gui.py`

Tkinter + matplotlib. Controls: scenario preset textbox (`ms, quality[, quality_end[, collision]]` per line), TLC caps dropdowns, Monte-Carlo checkbox, Run / Save-CSV buttons, KPI textbox (includes `search_cycles`).

3 stacked plots (shared x):
1. MCS decision + channel-quality twin axis, with **STAY green shading + bold amber vertical lines/bands marking SEARCH cycles** (`_spans(recs, value, attr="mode")`; imports `Patch`, `Line2D`).
2. Throughput achieved vs best.
3. PER = 1 − SR.

`parse_segments(text)` parses the preset textbox.

---

## 7. Docs & deliverables (under `doc/`)

| File | What |
|---|---|
| `tlc_sim_architecture.html` | **Interactive** architecture page (main teaching artefact). Clickable B1–B6 blocks, per-block detail (role, in/out mini-diagram, functions table, state trees, vertical flow diagram, "Simple example" mini-graph). Standalone cards: **"Search cycle over time"** timeline, **"When does a SEARCH cycle start? — the condition, made simple"** (two-lane decision graphic: failure=immediate, success=300 ms gate), **"Block summary"** table. |
| `TLC_Sim_Plan.md` | Implementation plan (recommends binding real C `rateScaleMng` via USFSTL for true fidelity; two time regimes; simulated clock; phases; KPIs). |
| `TLC_Hierarchy.docx` | Word doc: TLC hierarchy, inputs/outputs, refresh rates, typical values, configs, TOC. |
| `TLC_ForDummies.pptx` | Simple slide deck. |
| `tlc_playground.html` | SR-driven interactive playground (behaves per SR, not SNR). |
| `build_*.py` + `assets/` | Generators for the docx/pptx/playground. **Run them from inside `doc/`** (they look for `<script_dir>/assets`). |
| `TLC_Hierarchy.md` (at TLC_Sim root) | Original hierarchy markdown. |

---

## 8. Environment & gotchas

- **Python 3.14** system interpreter: `C:/Users/eisack/AppData/Local/Python/pythoncore-3.14-64/python.exe`. Installed: `python-docx`, `python-pptx`, `matplotlib`.
- **PowerShell**: chain with `;` (never `&&`). Open files/GUI externally with `Start-Process`.
- **Embedded VS Code browser caches `file://` aggressively** → when re-checking HTML edits, use `open_browser_page(forceNew=True, url=...?query=bustcache)`. External browser via `Start-Process` loads fresh.
- **`summary()` UnicodeEncodeError (cp1252)**: fixed by using ASCII dashes instead of box-drawing chars — keep it ASCII-safe when stdout is redirected.
- Run GUI + open doc:
  ```powershell
  Set-Location "c:\Users\eisack\OneDrive - Intel Corporation\Desktop\Efrat\TLC_Sim"
  Start-Process python -ArgumentList "gui.py"
  Start-Process "doc\tlc_sim_architecture.html"
  ```

---

## 9. Problems already solved (don't re-solve)

- Jittery ReferenceTLC (3059 switches) → climb-while-perfect / back-off-and-dwell → column-based search.
- Stuck at low rate (efficiency 0.015) → caused by eager dwell + guard; fixed by removing premature dwell.
- Search cycles "random/almost transparent" (181 searches) → added real firmware trigger; GUI now uses bold amber `axvline` + state shading.
- `summary()` Unicode crash under redirect → ASCII-safe.
- Confirmed (twice, from source) TLC has **no periodic search timer** and is **SR-driven, not SNR**.

---

## 10. Open ideas / likely next requests

- Expose `SUCCESS_LIMIT` / `FAIL_LIMIT` / search-interval as **GUI sliders**.
- Switch clock to **offered-load (Mbps) model** so dwell wall-time is realistic (~500 ms) and ms-timers behave (currently window time = frame-count × airtime → dwell is short at high PHY rates).
- **Bind the real C `rateScaleMng`** into `run_sim` via USFSTL for true fidelity (per `TLC_Sim_Plan.md`).
- Model the not-yet-modelled firmware behaviour from §3.3 (200 ms upscale guard, legacy limits, 10 s stat flush, faster BW recovery / jump-to-best-BW).
- Annotate GUI decision plot with NSS/BW/GI (column) changes, not just MCS.
- Add an explicit "no periodic timer — count-driven; 300 ms only rate-limits success searches" note on the HTML condition graphic.
- Clean up the dead unused `B4FLOW` const still present in the HTML (harmless).

---

## 11. Transcript pointer

Full uncompacted conversation transcript (for exact snippets/code):
```
c:\Users\eisack\AppData\Roaming\Code\User\workspaceStorage\33ef86635bcec206c8574fd5b0dcc230\GitHub.copilot-chat\transcripts\8d9dbd37-bb7d-4334-84b2-fda20d805af8.jsonl
```
