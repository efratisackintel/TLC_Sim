# TLC Simulation — Handoff & Lessons Notes

> Purpose: everything needed to **restart the conversation** without losing context.
> Scope: the `TLC_Sim` teaching/simulation project and the real firmware TLC facts it models.
> Last updated: 2026-10-14 (see §13.11 for the current insights and done / TBD list).

---

## 0. How to begin a new chat (paste this as your first prompt)

> I'm working on the TLC_Sim project (WiFi firmware TLC / rate-scaling teaching + simulation),
> in the multi-root workspace folder `TLC_Sim`.
>
> First, read `doc/TLC_Sim_Handoff.md` end-to-end to load full context — it's the up-to-date
> restart doc (project overview, the tlcsim/ B1–B6 engine, the browser playground, FW facts,
> and this project's history incl. delay-spread profiles, the FW-faithful retry table §3.5,
> the collision/SR analysis §11, the 2026-09 UI restructure + genie/lab & scale-action notes §12,
> and the 2026-10 real-sysmon replay, 320 MHz trap and FIX 1–9 work §13 — start with §13.11).
>
> Key things to keep in mind:
> - TWO engines that must stay in sync: the Python package `tlcsim/` (the real engine, run via
>   run_example.py / gui.py) and the browser JS in `doc/tlc_playground.html` (teaching artifact).
>   Any model change must be applied to BOTH.
> - FW source of truth (read-only, in the `wcd_fw-dev` folder):
>   fw/src/umac/main/dataPath/rateScaleMng/rateScaleMng.c (RS_MNG algorithm).
> - Verify HTML/playground changes by reloading in the browser; verify Python with run_example.py.
> - Git: current stable release is tag V1.0; latest work is committed (HEAD on main).
>   Do NOT commit/push/stage unless I explicitly ask.
>
> My task: <describe the task here>

**Non-negotiables for any session:**
1. **Read this doc first** — it is the single source of restart context.
2. **Two-engine parity** — every *model* change (PER, channel, retry table, ISI, thresholds)
   goes into BOTH `tlcsim/` (Python) and `doc/tlc_playground.html` (JS). Test/dev-only tooling
   can be Python-only, but note it.
3. **FW is read-only truth** — `rateScaleMng.c` in `wcd_fw-dev`; never edit it, cite it.
4. **Verify before claiming done** — Python via `run_example.py`; playground by reloading in the
   browser (force cache-bust for the embedded VS Code browser — see §8).
5. **Never commit/push/stage** unless explicitly asked. Stable release = tag `V1.0`; work on `main`.

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

> Sim caveat: because there is no real radio, the sim/playground **synthesizes** the SR feedback from measured **PER-vs-SNR** curves (B2) at the channel SNR. So the channel input is SNR, but the TLC decision is still made on the resulting Success Ratio — faithful to the FW's SR-driven objective.

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

### 3.4 FW telemetry mapping (uSniffer `sub_usniffer_ratescale.h` / `usniffer_globals.yaml`)

The real algorithm is **`RS_MNG` (Rate-Scale Manager, a.k.a. TLC)**, per-station in UMAC. Its uSniffer contracts confirm the design and give the exact vocabulary the sim mimics:

- **Search-cycle start reasons** (`searchCycleParams.startReason`) — the *only* four triggers, matching the sim's SUCCESS/GUARD/FAIL logic:
  1. `succeeded_frames_time` (time gate) · 2. `succeeded_frames` (count) · 3. `flush_time` (periodic stats flush) · 4. `failed_frames_threshold` (immediate).
  The sim implements 1/2/4; #3 (flush) is not modelled.
- **Scale action** (`USNIFFER_EVT_RS_MNG_SCALE_ACTION_S`): compares `currTpt` vs one-step-`lower`/`higher` rate TPT + `currSuccessRatio` → `STAY/UPSCALE/DOWNSCALE` with a reason (`higher_rate_has_higher_tpt`, `current_rate_has_highest_tpt`, `below_force_decrease_threshold`, …). Objective is **expected aggregated (airtime) throughput**, from real BlockAck `txed/acked`, NOT a PER-vs-SNR curve.
- **Columns** (`visitedColumns`, 22): `non_ht_ant_a/b`, `siso_ant_a/b`, `siso_stbc`, `mimo`, and HE GI variants `he_{0_8,1_6,3_2}_{siso,mimo}` (+`_sgi`). Each SC keeps a **stable** column and probes a **test** column (`searchColParams.decision = REVERT_TO_STABLE_COL | SWITCH_TO_TEST_COL`).
- **Power cap** (`USNIFFER_EVT_RS_MNG_POWER_CAP_S`): MIMO/SISO `maxPower`/`powerCap`, `forceSiso` — the real analogue of the playground's PSD penalty (driven by SAR/TAS/regulatory, not a formula).
- Note: the RS_MNG *decision source* is not in the `wcd_fw-dev` view here — only its telemetry/config structs and `tlcContext::LQCmdParams` are.

### 3.5 Retry table (LQ command) — FW facts + how the sim models it

**FW source of truth:** `_rsMngBuildRatesTbl()` / `_rsMngFillLQCmd()` in `fw/src/umac/main/dataPath/rateScaleMng/rateScaleMng.c` (~L2456 / L2709). The retry table = `LINK_QUALITY_CMD_API_S.rate_scale_table` (the "retry ladder"), pre-loaded into HW; the HW walks it **per-attempt** without re-invoking the rate algorithm.

- **The retry table is active in ALL states — dwell, search cycle, AND upscale probe.** The claim "retry table only active in dwell, not SC" is **FALSE** per the source. What is SC-specific is the **test window** (`LINK_QUAL_FLAGS_TEST_WINDOWS_MSK` + `uAggFrameCntInTestWin = RS_MNG_UPSCALE_AGG_FRAME_COUNT`), which only limits how many frames are *counted at the test rate* for the decision — delivery still falls back.
- **Entry 0 = the sent rate** (the *test* rate during a probe).
- **Search cycle** (`searchBetterTbl`): entry 0 = the test/search column rate; the **rest of the ladder is built from the STABLE column** (pre-search committed rate), per the FW comment *"only the initial rate should be of that column. The rest of the table is constructed from the 'stable' column."*
- **Upscale probe** (`tryingRateUpscale`): entry 0 = the higher MCS (**tried once**); the rest = the **previous known-good** (lower) MCS.
- **Dwell:** full descending ladder from the committed rate (INITIAL/SECONDARY/third rate counts, then GI↑/STBC/SISO/BW↓, then legacy).
- **Per-rate stats (not pooled):** SR for the decision is `acked/txed` **per rate**. A too-high probe's primary rate reads ~0% (so it's abandoned) while the fallback delivers → the 20×100-MPDU "is it 50%?" example: same-rate retry (collision) → 50%; drop-to-lower-rate (bad-rate) → primary 0% + fallback 100%, never a blended 50%.
- **Why the depth matters:** a failed primary is redelivered at the fallback rate within the same/next TXOP (BA is SIFS-fast for A-MPDU), so real throughput dips to **~the fallback rate, not zero**. RTS is the only *preventive* collision tool the FW uses today.

**Sim modeling (both engines, 2026-08-25):** `retry_tput()`/`retry_chain()` (`per_model.py`) and `retryTput()`/`retryChain()` (playground) build the chain FW-style — entry 0 = sent rate, fallbacks from the **stable column** during SC (`lq.stable` / `LinkQuality.stable`), from the primary for dwell/upscale. Throughput is **airtime-weighted** (delivered bits ÷ (failed-attempt + retry airtime)); the **rate decision still uses the primary-rate SR** so too-high rates are still abandoned. Playground shows the achieved line in **red** while the retry table is backfilling. Approximation: per-rung mean, no per-MPDU BA bitmap / SIFS-BA overhead.

---

## 4. The simulation package `tlcsim/` (6 blocks, one file per block)

Closed loop: **rate table → emulator → SR statistics → TLC decision → repeat**.
Pure stdlib; matplotlib only used by the GUI.

| Block | File | Role |
|---|---|---|
| B1 | `channel.py` | Time-varying channel (**SNR dB** + collision). `ChannelState(snr_db, collision)`, `Seg{ms, snr_db, snr_end?, collision}` supports constant or linear ramp. `SNR_MIN=-20`, `SNR_MAX=60`. |
| B2 | `per_model.py` | **Data-driven** PER — NO sigmoid. `per(rate, ch)` / `phy_per(rate, snr_db)` interpolate the measured EHT PER-vs-SNR curve for the rate, saturating to 1.0 below / 0.0 above the swept range; then `PER = 1-(1-PER_phy)(1-collision)`. Loads `tlcsim/data/per_lut.npz`. Also `sens_snr(rate)` (SNR@10% PER), `has_rate(rate)`, `lut_keys()`. |
| B3 | `emulator.py` | LMAC+PHY surrogate. `simulate_window(rate_table, ch, window_frames, monte_carlo, rng)` → `WindowStats{txed,acked,sr}`. Coarse `acked=round(N*(1-per))` or Monte-Carlo draws. |
| B4 | `tlc.py` | **The rate picker under test** (swap point). `ReferenceTLC` = column-based state machine. See §5. |
| B5 | `results.py` | `Record`, `RunResult.to_csv()`, `.summary()` (ASCII-safe KPIs). |
| B6 | `harness.py` | `run_sim(channel, tlc, config, frame_bytes, monte_carlo, seed, max_ms)` — closed loop + simulated clock. |

`rates.py` — `Rate{mcs,nss,bw,gi08}`; tables `BASE_TPT` (HE/EHT 80 MHz SISO 0.8µs MCS0-13 Mbps), `BW_FACTOR`, `GI08=1.0/GI32=0.85`, `BANDWIDTHS=[20,40,80,160,320]`; funcs `expected_tpt(r)`, `sens_snr(r)`, `all_rates()` (restricted to the LUT keys). **`MCS_Q`/`required_quality`/`BW_PENALTY`/`NSS_PENALTY` were removed** in the data-driven rework.

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

Validated: `fade_and_recover` / `run_example.py` → efficiency ~0.81 with the data-driven PER; climbs to high MCS·MIMO·wide-BW on a good channel and tracks fades; many short search cycles with the faithful count/guard trigger (emergent, no fixed timer).

---

## 6. GUI — `gui.py`

Tkinter + matplotlib. Controls: scenario preset textbox (`ms, quality[, quality_end[, collision]]` per line), TLC caps dropdowns, Monte-Carlo checkbox, Run / Save-CSV buttons, KPI textbox (includes `search_cycles`).

3 stacked plots (shared x):
1. MCS decision + channel-quality twin axis, with **STAY green shading + bold amber vertical lines/bands marking SEARCH cycles** (`_spans(recs, value, attr="mode")`; imports `Patch`, `Line2D`).
2. Throughput achieved vs best.
3. PER = 1 − SR.

`parse_segments(text)` parses the preset textbox.

> Engine parity: the GUI runs the **same `tlcsim` engine** via `run_sim`, so it **inherits** the retry-table (`retry_tput`) and delay-spread ISI automatically in its results. But it has **no UI for the new features** — `Seg(...)` is built without a profile, so the channel is always **AWGN (τ=0)**, and there is **no GI plot / no retry-red colouring** (those are playground-only). To exercise delay-spread/profiles in Python, use `run_example.py` / a script with `Seg(profile=...)`.

---

## 7. Docs & deliverables (under `doc/`)

| File | What |
|---|---|
| `tlc_playground.html` | **Primary interactive artefact.** **Four** tabs (tab bar `.ptabbar` / `showTab()`, deep-linkable via `#live`/`#scenario`/`#doc`/`#improve`): **🎛 Live decision** (SNR slider → chosen MCS/streams/BW/GI, all-MCS PER-vs-SNR chart; controls: **Band** (2.4/5/6), **Channel profile / delay spread** (awgn/small room/office/outdoor → τ), Max BW (**def 320**), Antennas (**def 2/MIMO**), PSD-penalty toggle), **📈 Simulation** (closed-loop scenario over time: **5 charts** — 0 throughput (achieved/best/**avg 100 ms**; achieved turns **red** while the retry table backfills), 1 MCS+SNR, 2 BW+SNR, 3 streams+SNR, 4 **GI+SNR** — SEARCH bands numbered, search-cycle log, KPIs incl. **time between SC** / **SC duration**; **drag to zoom all charts**; preset format `ms, SNR[, SNR_end[, collision[, profile]]]` with per-segment channel profile; presets incl. **sudden wall (LOS → long → LOS)**), **🏗 Architecture** and **💡 Improvements** (both lazy-loaded iframes; footer hidden on these tabs). |
| `tlc_sim_architecture.html` | The interactive architecture page (now embedded in the playground's Architecture tab **and** still standalone). Clickable B1–B6 block diagram + per-block detail (role, in/out mini-diagram, functions table, state trees, vertical flow, "Simple example"). **Left fixed POC/Contents nav** (`#poc`: 0 High level, 1 B1 … 6 B6, 7 Decisions, 8 TLC flow, 9 TX power) drives `show()` + scroll; the old middle B1–B6 tab-button row was removed. Integrated **PER Model Explorer** (`ex_`-prefixed, shown under B2). **B3 now carries a "What counts in the Success Ratio" panel** (SR decomposition: channel PER vs collision, stacked-bar SVG + table). |
| `tlc_sim_improvements.html` | **NEW (2026-08-24)** — the **💡 Improvements** tab (4th playground tab, `#improve`; loaded as an iframe like Architecture). Left `#poc`-style **Ideas** nav (`ideaGo()`). **Idea 1 — Handle collision**: problem (blended SR), proposed algorithm (split channel vs collision, don't down-scale for contention, protect with RTS/CTS), how-to-distinguish table, expected-impact table, and a **Test — collision scenario** section (setup preset, A/B pass-fail criteria, control checks, Python CI hook). |
| `per_model_explorer.html` | Standalone PER explorer — every measured PER curve per permutation, log-axis toggle, SNR marker, CSV export. |
| `TLC_Sim_Plan.md` | Implementation plan (recommends binding real C `rateScaleMng` via USFSTL for true fidelity; two time regimes; simulated clock; phases; KPIs). |
| `TLC_Hierarchy.docx` | Word doc: TLC hierarchy, inputs/outputs, refresh rates, typical values, configs, TOC. |
| `TLC_ForDummies.pptx` | Simple slide deck. |
| `build_*.py` + `assets/` | Generators for the docx/pptx/playground. **Run them from inside `doc/`** (they look for `<script_dir>/assets`). |
| `TLC_Hierarchy.md` (at TLC_Sim root) | Original hierarchy markdown. |
| `index.html` (at TLC_Sim root) | Landing page with 3 cards → Playground / Architecture (`#doc`) / PER Explorer. |

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
  Start-Process "doc\tlc_playground.html"
  ```

---

## 9. Problems already solved (don't re-solve)

- Jittery ReferenceTLC (3059 switches) → climb-while-perfect / back-off-and-dwell → column-based search.
- Stuck at low rate (efficiency 0.015) → caused by eager dwell + guard; fixed by removing premature dwell.
- Search cycles "random/almost transparent" (181 searches) → added real firmware trigger; GUI now uses bold amber `axvline` + state shading.
- `summary()` Unicode crash under redirect → ASCII-safe.
- Confirmed (twice, from source) TLC has **no periodic search timer** and is **SR-driven, not SNR**.
- **Data-driven PER rework** (this session's baseline): removed the analytic sigmoid entirely; B2 now interpolates measured EHT curves. SISO→`1x2` antenna, MIMO→`2x2` antenna mapping. `run_example.py` efficiency ~0.81.
- **Retry table now modeled (2026-08-25)** in BOTH engines: a failed primary is redelivered through a fallback chain via **airtime-weighted** throughput (`retry_tput` in `per_model.py`; `retryTput` in the playground). Built like the FW `_rsMngBuildRatesTbl`: **entry 0 = the sent/test rate**, and the fallback ladder is taken from the **stable column** — during a **search cycle the retry table is still active** (verified against `rateScaleMng.c:2456`), its fallbacks = the **pre-search committed rate** (not the test column); dwell/upscale base = primary. The **rate decision still uses the primary-rate SR** (unchanged), so a too-high rate is still abandoned — only the **throughput dip depth** is corrected (dips to ~fallback rate, not zero). Playground: achieved line turns **red** while retrying; avg line = **100 ms**. Approximation: per-rung mean, no per-MPDU BA bitmap / SIFS-BA overhead. NOTE: the claim "retry table only active in dwell, not SC" is **false** per the FW source.
- **Playground merge (2026-08-23)**: architecture doc merged into the playground as the **🏗 Architecture** iframe tab; renamed the standalone to `_old`; added left POC nav; removed the middle B1–B6 tab row; Simulation tab KPIs gained **time between SC** / **SC duration**; **default Max BW = 320 MHz**.
- **Double-scrollbar / narrow-iframe fixes**: doc panel must NOT reuse the `.wrap` class (it's a CSS grid → forced the iframe into a 360 px column); iframe height computed from its live top; footer hidden on the doc tab.

---

## 10. Open ideas / likely next requests

- Expose `SUCCESS_LIMIT` / `FAIL_LIMIT` / search-interval as **GUI sliders** (and in the playground Simulation tab, to reduce the many SCs on a healthy link).
- Switch clock to **offered-load (Mbps) model** so dwell wall-time is realistic (~500 ms) and ms-timers behave (currently window time = frame-count × airtime → dwell is short at high PHY rates).
- **Bind the real C `rateScaleMng`** into `run_sim` via USFSTL for true fidelity (per `TLC_Sim_Plan.md`).
- Model the not-yet-modelled firmware behaviour from §3.3 (200 ms upscale guard, legacy limits, 10 s stat flush, faster BW recovery / jump-to-best-BW).
- Annotate GUI decision plot with NSS/BW/GI (column) changes, not just MCS. *(Done in the browser Simulation tab — separate MCS / BW / streams charts; still open for the Tkinter GUI.)*
- Add an explicit "no periodic timer — count-driven; 300 ms only rate-limits success searches" note on the HTML condition graphic.
- Clean up the dead unused `B4FLOW` const still present in the HTML (harmless).
- **Improvement Idea 1 — Handle collision** (documented in `tlc_sim_improvements.html`): split channel vs collision loss; don't down-scale for contention; protect with RTS. **Partly done (2026-10-14) as FIX 9 (collision-aware downscale) and FIX 7 (CTS guard)** in the playground — see §13.10 / §13.11. Original note: prototype as an **opt-in "collision-aware TLC" toggle** in the Simulation tab (default OFF = FW-faithful) so the Improvements idea becomes a live A/B. Note: sim RTS is currently **cosmetic** (a flag) — to show Idea 1's benefit, RTS must actually lower the modeled collision rate.
- **Improvement Idea 2 — GI / channel-profile awareness** (see 11.4): **IMPLEMENTED (2026-08-24)** in BOTH engines. B1 carries `delay_spread_us` + named `PROFILES = {"awgn":0.0,"small room":0.5,"office":1.0,"outdoor":3.0}`; B2 adds a synthetic ISI penalty (`isi_penalty()`: SNR penalty `6dB×(τ/GI−1)` + PER floor `0.5·(1−e^−excess)`, tunable via `ISI_SNR_PENALTY_DB/ISI_FLOOR_MAX/ISI_FLOOR_SCALE`). Playground mirror added: a **Channel profile** selector on the Live tab + `isiPenalty()` in `perLookup()`. GI binary (0.8/3.2µs, no 1.6) → **outdoor forces GI 3.2**; **office keeps GI 0.8** at high SNR (its 11% floor beats the ~15% long-GI overhead); small room/awgn unaffected. τ=0 default = backward-compatible.
- **Fix the B3 doc caveat** (11.2): reword "real firmware separates the two…" → make clear FW counts collision/ACK losses together today; the distinguishing table is Idea 1 (proposed), not current behavior.

---

## 11. Session 2026-08-24 — key takeaways

### 11.1 Success-Ratio semantics: what counts, and the collision blind spot
- **SR blends two very different losses**: `SR = (1−PER)·(1−collision)`. Channel/PER loss is **rate-dependent** (lower MCS → (1−PER)↑); collision loss is **rate-INDEPENDENT** (same at every MCS).
- **The collision blind spot** (why achieved TPT falls below `best` on a collision drop): during a contention burst SR sits at, e.g., 0.6 at *every* rate. Since 0.6 < `SR_NO_DEC` (90%), the TLC keeps down-scaling → collapses to **MCS 1** (≈147 Mbps) while `best` (optimal rate × (1−collision)) stays ≈ 2900 Mbps. Dropping MCS **cannot** recover a collision, so throughput tanks. Verified in the Simulation tab `interference burst` preset.
- **The sim is FW-faithful here** — do NOT "fix" the sim to avoid the collapse: today's real RS_MNG behaves the same way (see 11.2). The collapse is the teaching point.

### 11.2 How today's firmware counts losses (per-MPDU Block-ACK accounting)
- RS_MNG accumulates `succ`/`att` (acked/txed) **per rate (column/MCS)** over its stat window (≈2000 MPDUs dwell / 20 probe).
- With A-MPDU + Block-ACK, results are tallied **per MPDU** from the BA bitmap. If the **whole BA is lost** (BA timeout — collision *or* lost ACK on the return path), **all MPDUs of that aggregate count as failures**, even if the data was actually delivered.
- **Worked example** (user's): 2 PPDUs × 100 MPDUs at the same rate — #1 loses its BA (100 counted failed), #2 has 50 CRC errors (50 failed). Combined: `att=200, succ=50` → **PER = 75%, SR = 25%**. The lost-BA aggregate may really have delivered all 100 → SR **over-penalizes** (true delivery could be 75%). RS_MNG can't tell; it just down-scales.
- **Collision & ACK/BA losses ARE counted in the SR today** — there is **no split by cause**. The only current mitigation is **RTS/CTS** (preventive: fewer collisions), not corrective (it doesn't remove logged failures). Robustly separating the causes is exactly **Improvement Idea 1**.
- **Doc caveat to fix later**: the B3 note still says "real firmware separates the two… collision-only losses don't force a down-scale" — that is **aspirational (Idea 1), not today's behavior**. Reword to make clear FW counts them together; the BA-bitmap/CCA/RSSI signals are what Idea 1 *would* exploit.

### 11.3 Detection fingerprints (basis for Idea 1)
| Signal | Collision / BA-loss | Bad rate / channel |
|---|---|---|
| Loss vs MCS | flat (rate-independent) | grows with MCS |
| BA bitmap | whole A-MPDU lost (all-or-nothing) | partial / scattered |
| CCA at TX | medium busy | medium clear |
| RSSI trend | still strong | dropping |
| Right response | RTS/CTS, **hold** rate | down-scale MCS/BW |

### 11.4 PER model = **AWGN only** (channel-length / delay-spread finding)
- Verified by scanning the full `.fig` source behind `PERModel/per_catalog.npz`: **78 figs, 25,536 curves, 100% `Channel = AWGN`, `PPM = 0`**. There are **no** channel-D / TGn / multipath curves.
- Catalog key = `frameBW, channelBW, antenna, GI, MCS` — **no channel-type dimension**. GI (0.8/1.6/3.2) **is** a dimension, but under AWGN (zero delay spread) a longer GI only adds cyclic-prefix overhead with **no robustness benefit** → **GI 0.8 always wins today** (GI selection is effectively inert).
- **Recommended approach to add channel length** (LOS ≈0.5µs→GI 0.8, office ≈1µs→GI 1.6, outdoor ≈3µs→GI 3.2): **layer a GI-vs-delay-spread penalty on the AWGN curves** (no new measured data needed). Add a **channel profile** (RMS delay spread τ) in B1; in B2, when **GI < τ** apply an ISI **error floor + SNR cap** (exponential PDP: leaked fraction ρ ≈ e^(−T_GI/τ) → SINR cap ≈ −10log₁₀ρ, `PER_eff = per_awgn(min(snr, SINR_max))` floored at ρ); when **GI ≥ τ**, no floor → AWGN as-is. This makes GI selection meaningful and emerges naturally from the existing search. Alternatives: (B) obtain real multipath curves + add `Channel` as a real dimension (gold standard, no data available); (C) static `(profile, GI)` offset table (simplest; good as the tunable knobs behind A). **Chosen direction: A with C's table as parameters** — becomes **Improvement Idea 2 — GI / channel-profile awareness**, opt-in so AWGN stays default.

---

## 12. Session 2026-09-09 → 09-14 — UI restructure + genie/lab & scale-action insights

### 12.1 Playground UI changes (`doc/tlc_playground.html`, JS-only teaching artifact)
- **Simulation tab now has a left POC sidebar** (`#simpoc`), mirroring the Architecture tab. The old horizontal sub-tab bar at the top was **removed**. Four sub-sections switch via `showSub(which)`: `sim` (📈 Simulation — charts & run), `engine` (⚙️ Behind the scenes), `guide` (⚙️ How to configure — scenario/preset syntax), `about` (💡 What is this? — for-dummies). `showSub()` toggles `#simpoc a.active`; content wrapped in `.simlayout` (flex) + `.simcontent`. Sidebar auto-hides `@media(max-width:820px)`.
- **TVA per-step log toolbar decluttered**: only **📥 Save table → XLSX** and **🔬 Compare with lab log** show by default. The refine controls (Lab log dropdown, 📂 Browse, ✕ Clear lab, RSSI→SNR offset, 🎯 Auto-align) live in a hidden `#labControls` div revealed on Compare (`loadLabPreset()`/`loadLabFile()` set it to flex; `clearLab()` hides it).

### 12.2 Architecture tab changes (`doc/tlc_sim_architecture.html`)
- **`#poc` converted from `position:fixed` → sticky left sidebar** inside a `.layout` flex (`.wrap` = flex:1). It used to vanish under 1460px; breakpoint lowered to 820px so it stays visible on normal screens.
- **New B4-only card `card_expectedTpt`** — the firmware `expectedTptHe` throughput tables (GI 0.8µs and 3.2µs; all BW × SISO/MIMO × MCS0-13, in Mbps). Toggled visible only when B4 is active (in `show()` + hidden in `showExtra()`), same pattern as `card_searchTime`/`card_searchCond`.

### 12.3 Combined TVA workbook
- **`PERModel/build_tva_combined.py`** (new) generates **one** `Results/tva_sim_vs_lab_ALL.xlsx` with, per BW (20/40/80/160/320): sheets `TVA <bw>MHz`, `Charts <bw>MHz` (5 line charts), hidden `Data <bw>MHz`, plus one shared `RSSI to SNR`. It **imports helpers from `build_tva_compare`** (`run_bw`, `EXP_TPT_HE`, styling) and regenerates from source — so it does not read (or get blocked by) the per-BW files if they are open in Excel. Also committed: `Results/TVA V0/` and `TVA V1/` reference sets.

### 12.4 FW `expectedTptHe` — where it lives
- Table: `expectedTptHe[BW][GI][NSS][MCS]` in `fw/src/umac/main/dataPath/rateScaleMng/rateScaleMng.c` (~L336). Declared `_rateScaleMng.h` (~L879); read via `_rsMngGetExpectedTptTable()` (~L3145). **Stored as Mbps × 10.** Under **UMAC**. The sim's `EXP_TPT_HE` (playground) / `tlcsim/rates.py` mirror it verbatim. Top cell `320·MIMO·0.8µs·MCS13 = 5040 Mbps`.

### 12.5 Genie vs lab throughput gap (esp. 320 MHz) — analysis
- **They measure different things.** `genie`/`sim tpt = expectedTptHe × SR` (measured-PER-driven, but an **idealized upper bound**). `lab tpt` = real measured throughput, **~7 s averaged**. Matching MCS/BW/NSS/GI ⇒ same **PHY config**, NOT same Mbps.
- **The model does NOT simulate MAC/aggregation ceilings** (A-MPDU byte cap, Block-ACK, TXOP/PPDU-duration). Those overheads exist only in the real lab number, so lab sits **~10-20% below** genie even at identical rates.
- **320 MHz shows it most**: absolute Mbps are ~5000, so a ~12% efficiency gap is a huge (~400-900 Mbps) visual separation; the top-rate `expectedTpt` values are the most optimistic; several lab rows have residual SR 92-98% that further cut lab tpt.
- **README "Lessons learned" confirms**: genie is an idealized upper bound; the ~99% claim is **sim-vs-genie**, and 1 s sim windows vs ~7 s lab averaging explain the low-SNR-tail residuals. SNR 29 row: lab actually beats genie (metrics are independent). SNR 23: extra gap is a real rate mismatch (lab MCS7 vs genie MCS8).

### 12.6 PR can change WITHOUT a search cycle — scale action vs search cycle
- **Two independent mechanisms move the PR:** (a) **scale action** — in `STAY`, step MCS ±1 **within the current column** every stat window, SR-driven; (b) **search cycle** — in `SEARCH`, explore neighbouring columns (BW/NSS/GI). Only (b) is a numbered SC / orange band.
- **Sudden-drop trace (preset `1700,40 / 1700,8 / 1600,40`):** between SC6 (ends ~t=1540ms) and SC7 (starts ~t=1878ms) the state stays `STAY`. At t≈1702ms SNR drops 40→8, MCS13 SR→0%, and STAY **force-downscales** 13→12→…→2 (one MCS per window, since SR<`FORCE`=0.15) with **no search**. It parks at MCS2/100% SR, then SC7 fires later once the success counter + ~300 ms guard trip (a SUCCESS-triggered probe-up).
- **Gotcha:** during that descent the log shows `mode:"search"` but `state:"STAY"` — `mode` is only the **window length** (short 20-frame fast-fail vs 2000-frame dwell), not the SC counter. SC bands come from `state==='SEARCH'` spans.
- **Code (playground):** STAY scaling ~L1071 in `tlc_playground.html`; constants `C={FORCE:.15, NODEC:.90, PERF:.95, SEARCH:20, DWELL:2000, FAIL:400, SUCC:4500, GUARD:300, UPGUARD:200}`. Maps to FW `SCALE_ACTION` (up/down-scale) vs `SEARCH_CYCLE` (column switch).

### 12.7 Git state
- Commit **`5f7a104`** (2026-09-09, on `main`, pushed to `origin` = `github.com/efratisackintel/TLC_Sim`): all of 12.1-12.3.
- **Uncommitted:** `TLC_Sim.code-workspace` adds the `../Agents` folder to the multi-root workspace (3 lines) — not staged.

---

## 13. Session 2026-10-12 — real sysmon replay, wide-BW (320) trap, fixes A/B

### 13.1 The real case (`Logs/TLC/ZoharBadLog.sysmon`, Scorpius2-Whp, 6 GHz UHB, uplink, 13.3 s)
- Link sits at the bottom: **M1·SISO·160** (SR 100%) / **M0·MIMO·160** (81%); M2·160 ≈ 50%. Tpt ≈ 90–130 Mbps.
- **M0·SISO·320 SR = 17%** (whole A-MPDU losses, BA timeouts) — far worse than the SNR explains → bursty loss on the upper 160 (OBSS / hidden node at the AP).
- Every SC (~500 ms) tries 160→320. Twice (t≈7.4 s and 9.8 s) the **single 20-MPDU test window passed by luck** (`testTpt >= stableTpt`, rateScaleMng.c ~L4810) → `SWITCH_TO_TEST_COL`; the stable column's stats are cleared (`_rsMngSwitchToSearchCol`), in-column downscale lands on **M0/320** and the SC ends there.
- At MCS 0 there is no in-column escape; the FAIL-triggered SCs then **start and end at once** because `avoidHigherMcs` is set (prev SR ≥95% → <70%, L5593; `_rsMngSearchBetterCol` returns FALSE, L3932) for `RS_MNG_UPSCALE_IGNORE_HIGHER_MCS` = 1 s → ~1.2 s at ~1–15 Mbps per trap. Recovery = first SC after the timeout, via the M0/160 test (target = measured tpt when SR ≤ 90%).
- **uSniffer label gotcha:** `startReason` code 3 prints as `flush_time`, but FW enum `RS_MNG_SEARCH_CYCLE_START_REASON_E` value 3 = **FAIL_FRAMES** (2 = FAIL = FLUSH_TIME alias). Code 0 (unlabelled) = SUCCESS_TIME.
- TX_RATE_SCALE: `success`=all acked flag, `txed_vs_acked` = **failed** MPDUs (matches RS_MNG_STATISTICS primary txed/acked).

### 13.2 Playground additions (`doc/tlc_playground.html`, Simulation tab)
- **Mode bar** (`setSimMode(m)`, `SIM_MODE`, default 2): **1 Synthetic** (segments only, lab cleared) · **2 Lab TVA sweep (JSON)** (`.labOnly` controls + bundled `LAB_REF`, TVA sweep preset if <5 segments) · **3 Real trace (sysmon)** (`#traceCard` shown, TVA table hidden, pink overlay only here; re-runs Recreate on entry if a trace is loaded). `⚙️ Engine options & fixes` card + ⚖ A/B are common to all modes.
- **🔬 Real trace replay**: loads a `.sysmon` text trace (streamed + parsed in the browser, ~2 s for 92 MB) or a `.replay.json` from **`tools/sysmon_to_replay.py`** (same layout). Overlays the real PR (LQ `rate0`), 100 ms tpt and SC spans in **pink** on all 5 charts; real SC log (wider-BW commits ⚠, blocked ⛔); per-rate SR table.
- **🧪 Recreate**: fits effective SNR to per-rate SR at ≤ main BW (RSSI unused), then `obss<bw>=P` for wider BWs; sets band/Max BW/antennas; picks the closest of 30 Monte-Carlo seeds. Result for this trace: `13336, 1.5, -, 0.01, awgn, obss320=0.83`.
- New segment token **`obss<bw>=P`** (whole-A-MPDU loss at ≥ bw). New preset *wide-BW trap (OBSS on upper 160)*.
- **Monte-Carlo** (checkbox + seed): `mcWindow()` — A-MPDUs ≤5.4 ms, bursty per-PPDU hit, per-MPDU PER, retry rungs one 5.4 ms PPDU each (dwell sends the initial rate twice, `INITIAL_RATE_NUM=2`), dwell windows = 5 A-MPDUs.
- **FW-exact** (`opt.fw`): avoid-higher-MCS (blocks upscale + SC 1 s, blocked SCs logged), incumbent = measured tpt, SC target = measured tpt when SR ≤ 90%. **Always on in the playground since 2026-10-13** (checkbox removed; standard presets moved slightly, e.g. sudden drop 2594→2640 Mbps). Python `ReferenceTLC(fw=)` stays **opt-in** — with fw on its simpler TLC collapses on the standard scenarios (e.g. sudden_drop 1235→38 Mbps); `tools/replay_ab.py` sets it explicitly.
- **Fixes** (`makeTLC` opts): FIX 1 `wideConfirm` (3 passing test windows for a wider BW), FIX 2 `floorEscape` (MCS 0 & SR<50% → SC now, ignores avoid, never wider), FIX 3 `wideBackoff` (BW left <3 s after commit barred 2→16 s).
- **⚖ A/B** (N seeds): real trace vs baseline vs each fix vs all → avg Mbps, drop time (100 ms bins < 40% of real median), time >160 MHz, wider-BW commits, blocked SCs.
- All new behaviour is **opt-in**; with the checkboxes off every existing preset gives identical KPIs (verified vs HEAD).

### 13.3 Results (20–40 seeds)
| | avg Mbps | drop s | s >160 | wider commits |
|---|---|---|---|---|
| Real trace | 87 | 2.70 | 2.62 | 2 |
| Sim, current FW | 84–86 | 2.2–2.6 | 2.7–3.1 | 2.3–2.4 |
| + FIX 1 | ~101 | ~0.1 | ~0.1 | 0.1 |
| + FIX 2 | ~89 | ~1.8 | ~2.0 | ~1.6 |
| + FIX 3 | ~89 | ~1.9 | ~2.2 | ~1.9 |
| all | ~101 | ~0.0 | ~0.0 | 0.1 |
- Known gaps: sim blocked-SC count ~20 vs real 4 (sim retry airtime per failed A-MPDU shorter → FAIL counter fills faster); AWGN LUT makes GI 3.2 (4×LTF) ~1 dB better at low SNR so the sim prefers M2·3.2 µs where FW used M1·0.8 µs; real MIMO penalty (81%) not in AWGN.
- **Closed (2026-10-13):** fit now uses first-transmission A-MPDUs only; SNR from SISO short-GI rates, then segment tokens **`mimo=<dB>`** / **`lgi=<dB>`** (extra SNR loss for MIMO / long GI, `PEN_OVERRIDE` in `perLookup`; Python `Seg(mimo_db=, lgi_db=)`). Fit for ZoharBadLog: `13336, 1.5, -, 0.01, awgn, obss320=0.79, mimo=2, lgi=0.5` (rms 2%). Monte-Carlo dwell windows add **`MC_FAIL_S` = 10 ms** per A-MPDU with no ACK (BA timeout + backoff; Python `emulator.FAIL_S`), fitted to the real trap timing. Mode-3 "Real log vs simulated FW" table (`renderTraceCompare`) now matches on all rows incl. most-used rate (M1·SISO·160·0.8 µs).

### 13.4 Python parity (done 2026-10-13, all opt-in; defaults byte-identical — `tlc_run.csv` unchanged)
- B1 `Seg(obss={320: P})` / `ChannelState.loss(bw)`; B2 `per()` uses it, new `phy_fail()`.
- B3 `simulate_window_mc()` + `ppdu_frames()` (= playground `mcWindow`); B6 `run_sim(..., mc_ppdu=True)`; B5 `RunResult.events` (search-cycle log incl. blocked).
- B4 `ReferenceTLC(fw=, wide_confirm=, floor_escape=, wide_backoff=, init_rate=)`. `fw` also adds the 200 ms upscale guard and 300 ms stale-window reset (the playground already had both). Also fixed: MCS no longer decrements below 0.
- `scenarios.wide_bw_trap()`; **`tools/replay_ab.py <trace.sysmon|.replay.json> [--seeds N] [--csv]`** = the playground's Recreate + A/B in Python (~2 s for 20 seeds).
- Python baseline traps harder than the playground (drop ≈3.8 s vs real 2.7; ReferenceTLC lacks the JS MCS cooldown); fix ranking is the same: FIX 1 ≫ FIX 2 > FIX 3.
- Not ported: `gui.py` has no UI for these options; `PERModel/build_tva_compare.py` (deterministic TVA port) unchanged.

### 13.5 Shared interference timeline (common random numbers, 2026-10-13)
- Monte-Carlo whole-A-MPDU loss is now a **fixed busy/free timeline per seed** (`busyAt` / Python `emulator.busy_at`): one hashed draw per **5.9 ms slot** (A-MPDU + overhead) and per source (collision, each `obss<bw>`), independent of TLC decisions. Every variant with the same seed meets the same bursts at the same times → current FW and FIX runs coincide until a decision differs, and drops line up. Per-MPDU PER outcomes are also keyed by (seed, rate, slot, MPDU index) — no sequential RNG in the MC window — so the same action at the same time always gets the same result; variants diverge only where their logic acts.
- Mode-3 throughput chart: real + current FW + dashed FIX 1/2/3 lines (same seed, `TR_VARS`), one "on 320 MHz" strip per series; comparison table moved to its own card (`#cmpCard`) under the chart with one column per fix.
- FIX 2 bug fixed: a FLOOR search is no longer cut short by avoid-higher-MCS (it stopped after the first column).
- **Finding:** with time-correlated interference FIX 1 weakens (20 seeds, playground: drop 3.33 → 1.39 s; Python 3.44 → 1.87 s) because its 3 back-to-back test windows (~7 ms) fall in the same free gap. Confirmation should be **spread in time**. FIX 2 now helps (1.71 / 0.44 s); all three ≈ 0.1–0.7 s.

### 13.6 Trap moments scripted from the log (`quiet<bw>=t1/t2`, 2026-10-14)
- Goal: the drop appears at the **same place for every algorithm**, so a fix is judged on the real trap, not on dodging random luck.
- Token `quiet320=7.37/9.69` (s; real search cycles that committed 320) + optional `gap=<ms>` (default **5 ms** = one 20-frame test; the log's first dwell stat after the lucky test was 0/61). Engine: `busyAt(ch,bw,t,seed,opp,dwell)` / Python `busy_at(..., opp, dwell)`, `Seg/ChannelState.quiet`, `quiet_gap_ms`.
- Rules: at BW ≥ 320, **tests** are always blocked except one quiet gap per opportunity; the gap opens at the first 320 transmission in **[t − 300 ms, t + 600 ms]** (> one ~0.53 s search period). If that window still fails (e.g. a MIMO test at 1.5 dB) the opportunity is refunded. **Dwell** traffic outside the gap sees `obss320` (in-trap SR ≈ 20%, as in the log). Without `quiet`, behaviour is unchanged (regression byte-identical).
- Playground: checkbox **"trap moments from the log"** (trace card, default on, persisted); recreate emits both `obss320` and `quiet320`. Python: `replay_ab.py` uses it by default, `--random-traps` to disable, `--gap ms`.
- Results, 20 seeds (playground avg Mbps / drop s): FW 87 / 2.04 (real 87 / 2.70); FIX 1 88 / 1.90; FIX 2 94 / 0.91; FIX 3 92 / 1.34; all 96 / 0.67. Python: FW 89 / 1.75, FIX 1 90 / 1.67, FIX 2 84 / 0.07, FIX 3 93 / 1.25.
- **Sensitivity:** only FIX 1 depends on the gap length: gap 3 ms → FIX 1 removes both traps (2nd confirm fails); gap ≥ 5 ms → all 3 confirms pass, no gain. The log only bounds the gap to 2–44 ms, so FIX 1's value is unproven; FIX 2 / FIX 3 are robust to it.
- **Bug fixed (Monte-Carlo A-MPDU cap):** `mcPpduFrames` / `ppdu_frames` capped a PPDU at 256 × 1500 B, so at MCS 13/320 MIMO a PPDU was 0.61 ms + 0.5 ms overhead → 55% of PHY (TVA mode showed 2751 vs lab 4607 Mbps). Now airtime-limited only (5.4 ms; EHT 1024 BA × A-MSDU never binds) → 4530 vs lab 4607. Low-rate runs (ZoharBadLog) and the default regression are unchanged.

### 13.7 RTS/CTS evidence + CTS guard (was FIX 8, now FIX 7), fix proposals page (2026-10-14)
- Log (scripts `.claude/.temp/scratch/rts_seq.py`): RTS precedes every A-MPDU. No CTS: RTS@320 **81%**, RTS@160 26%, RTS@20 7%. After a CTS, data@320 got no BA 83% (data@160 9%). From 0–7 s every 320 test RTS went unanswered; the lucky test window had 6/23 CTS. FW does not narrow data BW after CTS (`punc_bw_index` stays 320); RX CTS always logged at 20 MHz (static vs dynamic BW unknown).
- FIX 8 `opt.ctsGuard` / Python `cts_guard`: EWMA CTS ratio per BW; wider BW with ratio < 50% of the next narrower BW's is never committed, and a committed one is left at once (reason `CTS`, narrower/other columns, bypasses avoid). Model: `ctsFail` / `cts_fail` = busy at the RTS time ignoring the quiet gap; deterministic mode uses 1 − loss(bw).
- 200 seeds (playground): FW 88 Mbps / 1.92 s → FIX 8 100 / 0.06 s; all simulated 101 / 0.04 s. Python 40 seeds: 89.8 / 1.64 → 99.5 / 0.24. TVA and all synthetic presets identical with FIX 8.
- `doc/tlc_fix_proposals.html`: short what / why / who / risk page for FIX 1–8 (4–7 = retry-table and LMAC proposals from the user, not simulated yet), linked from the playground's fixes card.

### 13.8 FIX 4–6 simulated (playground only; Python not ported yet) — numbering final: CTS guard = FIX 7
- `opt.gprNet` (FIX 4): past statistics `hist` = measured tpt per primary rate, kept for the last 10 search cycles; GPR1/2 into retry slots 2–3 (after rate0×2) if peak ≤ rate0's. `opt.banBpr` (FIX 5): primary < 50% of GPR1 tpt for 2 windows and wider BW / more streams than GPR1 → that BW / NSS banned 2 s (`bprBw`/`bprNss`, filtered in `neigh`), search reason `BPR` (bypasses avoid, incumbent −1).
- **FIX 6 = `opt.sdTable` + `opt.lmacStay` together** (user's intent: 320 fails → the step-down line 160 succeeds → the next A-MPDU starts on 160, not back on 320). `retryChain(p,base,ext)` dwell table = rate0, GPRs, SD(rate0), SD(GPRs), … down to M0·20 (SD = MCS−1, BW/2, SISO, long GI; dedup). `mcWindow` starts each A-MPDU at `lmac.start` (last line with ≥ 50% success; back up one line after 4 successes; reset when the table changes); TLC stats = rate0 first attempts only, window with none → no `onStats`. (An earlier standalone "LMAC stay" FIX 7 was a misreading — alone it parks on the old table's 20 MHz entry: 63 Mbps / 5.3 s — removed.)
- CTS guard renumbered **FIX 8 → FIX 7** (ids `fix7`/`showF7`, `TR_VARS.fix7`, Python docstrings, `replay_ab.py`).
- 200 seeds: FIX 4 91 / 1.61 s, FIX 5 94 / 0.81, FIX 6 92 / 1.41, FIX 4+6 95 / 0.96, FIX 7 (CTS) 100 / 0.06, all 1–7 101 / 0.02. Side effects (5 seeds): FIX 6 −20% on "interference burst" (collisions push the LMAC to a ~¼-rate SD line), FIX 4+6 −23%; FIX 6 −3% on the deterministic TVA sweep; FIX 4/5/7 neutral.

### 13.9 FIX 8 — early termination of fatal degradation (user's slide, DCR priority 3)
- `opt.earlyTerm`: after a search commits a new column (`colSince`), every STAY window is kept in `etWin` (last `ET_MS`=80 ms). Once ≥ 80 ms on the column, if avg SR ≤ `ET_THR`=30% × GPR1 SR or avg tpt ≤ 30% × GPR1 tpt (GPR1 = best `hist` entry of a different column, last 10 SCs; `hist` now stores `sr`) → SC event reason `EARLY`, primary := GPR1 at once (bypasses search/avoid).
- Slide text says "restore BPR1 TLC operation table" — implemented as restoring **GPR1** (asked the user to confirm).
- 200 seeds: 96 Mbps / 0.65 s (FW 88 / 1.92); all 1–8 101 / 0.01. Side effects (5 seeds): interference burst +19%, sudden wall −6% (stale GPR1 after a whole-channel drop), fade & recover −2%; TVA unchanged.

### 13.10 FIX 9 collision-aware downscale + high-SNR regression (2026-10-14)
- `opt.collAware`: `mcWindow` returns per-window `primPP`, `noBaPP` (primary A-MPDUs with 0 acked), `baTx/baOk`; if 0 < noBaPP ≤ 50% of primPP the TLC gets `acked = baOk/baTx·N` (SR without the whole-lost A-MPDUs), else the true count. Deterministic: if hit(bw) ≤ 0.5 → acked = N·(1−PER).
- `HS_SCN` + `runRegression()` (button **🧪 Regression**): first column = **ZoharBadLog drops** (fitted line with `quiet320`, shows avg Mbps + drop s, threshold 40% of the real median or 41 Mbps), then 6 scenarios at 320 MHz/2 streams (clean 45 dB, TVA 50→35, 35 dB, 45 dB + 2% / 10% collisions, 45 dB with OBSS 2 s), all AB_VARIANTS, `abSeeds` (≤ 20) seeds.
- Findings: clean high-SNR link = 90% of genie (A-MPDU overhead), no fix changes it. Collisions dominate: FW 2% → 67% of genie, 10% → 19%. FIX 9: +10% / +217% there, +70% "steady", +38% "interference burst", 0 elsewhere; ZoharBadLog 90 Mbps / 2.24 s alone; all 1–9 106 Mbps / 0.06 s (achievable ceiling ≈ 109). FIX 1/3/5/6 lose 8–32% at 10% collisions; FIX 2/6/7 −8 to −10% after a 2 s OBSS burst (slow return to 320).
- The 7 regression cases are also **🧪 preset buttons** in the Channel scenario card (each sets Max BW 320, 2 antennas, Monte-Carlo).
- Throughput chart title shows the **genie** rate + avg tpt (`genieTxt()`): ZoharBadLog genie = M1·SISO·160·0.8 µs, 121 Mbps.

### 13.11 Insights & status — sessions 2026-10-12 → 10-14 (read this first)

**Key insights**
1. **Root cause of the drops (ZoharBadLog):** one lucky 20-frame 320 MHz test (= 1 A-MPDU) commits 320; SR there ~20% (upper 160 busy at the receiver); BA stats can't tell "secondary busy" from "MCS too high" → MCS falls to 0 on 320; avoid-higher-MCS (`rateScaleMng.c` ~L5593/L3932) freezes all searches 1 s; the 320 retry table falls straight to 20 MHz → ~10 Mbps for ~1 s, twice.
2. **The evidence was in the log:** RTS precedes every A-MPDU; no CTS on 81% of RTS@320 vs 26% @160 (for 7 s before the first trap); after a CTS, data@320 got no BA 83% vs 9% @160. The FW never uses it (data BW not narrowed after CTS; CTS failures not in the TLC SR).
3. **A real log can't be replayed under a different algorithm** past the first divergent decision (no outcomes for rates not tried). Hence: fit a channel from the log + make randomness fair — common random numbers (fixed interference timeline per seed, PER keyed by time) and **scripted trap moments** (`quiet320`) so every algorithm meets the same traps. Average over seeds, not longer runs.
4. **Simulator calibration:** Monte-Carlo A-MPDU was capped at 256 × 1500 B → 55% of PHY at MCS13/320 (fixed: airtime-limited only, TVA now matches lab within ~3% at high SNR). A clean link tops out at ~90% of genie (0.5 ms overhead per 5.4 ms A-MPDU): **genie 121 Mbps vs achievable ~109 Mbps** on ZoharBadLog. Deterministic mode = best for rate-choice comparison vs lab (TVA mode defaults to it); Monte-Carlo = best for absolute throughput / real traces, but under-reads mid-SNR (26–32 dB) TVA steps (random SR dips trip avoid-higher-MCS).
5. **Collisions are the biggest loss at high SNR** (FW: 2% collisions → 67% of genie, 10% → 19%): one whole-lost A-MPDU in a 5-A-MPDU window → SR 80% → MCS down + 1 s cooldown. Same blind spot as the 320 trap, other dimension. (Magnitude depends on the FW stat-window size — validate on a real high-rate log.)
6. **Hold-offs need a fast way back:** bans / guards that are right for a permanent neighbour (ZoharBadLog) cost 8–10% when the OBSS is transient (2 s burst); fixes that read collisions as "this BW / rate is bad" (FIX 1/3/5/6) lose 8–32% under heavy collisions. Every fix must pass the 🧪 Regression set, not only the trap.
7. **Retry table + LMAC "stay on the line that succeeded" only helps with a good intermediate line** (160 after 320); with today's table it parks on 20 MHz and starves the TLC of primary stats (TLC goes blind).
8. **Remaining gap after all fixes** (106 vs ~109 achievable): collision downscales (now FIX 9) and the M0·MIMO vs M1·SISO tie (equal expected tpt, MIMO SR ~81%).
9. **Better design direction ("TLC 2.0")**: Observe (BA holes vs no BA, CTS per BW, RSSI, retry lines) → Diagnose the cause → act in that dimension; smarter search (confidence bounds on time-spread A-MPDUs, Minstrel-style in-traffic probing, per-column memory, real-goodput objective); Protect (time-limited probation with safety-net table + revert; direction-only guard instead of the global 1 s freeze). The 9 fixes map onto 3 mechanisms.

**Fix status** (ZoharBadLog: 200 seeds, playground; FW 88 Mbps / 1.92 s, real 87 / 2.70)

| # | Fix | Playground | Python | Trap result | Regression note |
|---|---|---|---|---|---|
| 1 | Confirm wider BW (3 windows) | ✅ | ✅ | 88 / 1.83 s | −12% @10% coll.; needs time-spread form |
| 2 | Escape MCS-0 floor | ✅ | ✅ | 93 / 0.92 s | −9% transient OBSS |
| 3 | Wider-BW backoff 2→16 s | ✅ | ✅ | 93 / 1.22 s | −12% @10% coll. |
| 4 | GPR safety net (retry slots 3–4) | ✅ | ❌ | 91 / 1.61 s | neutral |
| 5 | Ban bad primary rates 2 s | ✅ | ❌ | 94 / 0.81 s | −8% @10% coll. |
| 6 | Step-down table + start on last good line | ✅ | ❌ | 92 / 1.41 s (4+6: 95 / 0.96) | −32% @10% coll., −10% transient OBSS, −3% TVA |
| 7 | CTS guard (RTS/CTS per BW) | ✅ | ✅ | **100 / 0.06 s** | −8% transient OBSS (slow CTS-EWMA recovery) |
| 8 | Early termination (80 ms, 30% of GPR1) | ✅ | ❌ | 96 / 0.65 s | +17% @10% coll., −6% sudden wall (stale GPR1) |
| 9 | Collision-aware downscale | ✅ | ❌ | 90 / 2.24 s | **+70% steady, +217% @10% coll.**, 0 on clean |
| all | 1–9 | ✅ | — | **106 / 0.06 s** | |

Current recommendation: **FIX 7 + FIX 9 + FIX 8**; FIX 1/3/5/6 only once made collision-aware (trigger on CTS / BA-timeout signals, not raw SR).

**TLC 2.0 status**

| Stage / idea | Status |
|---|---|
| Observe: BA holes vs no BA | ✅ (FIX 9) |
| Observe: CTS answered per BW | ✅ (FIX 7) |
| Observe: dynamic-BW CTS (which BW is clear) | ❌ TBD — not modelled; FW question (log shows every CTS at 20 MHz) |
| Observe: RSSI trend | ❌ TBD |
| Observe: retry-line outcomes | 🟡 used by FIX 6 for the start line, not as a diagnosis |
| Diagnose: secondary busy → BW down | ✅ (FIX 7) |
| Diagnose: collision → hold MCS | ✅ (FIX 9) |
| Diagnose: MIMO ≪ SISO SR at equal tpt → SISO (FIX 10 tie-break) | ❌ TBD |
| Diagnose: one unified classifier | ❌ TBD (today separate options) |
| Search: confidence bound, time-spread samples | ❌ TBD |
| Search: Minstrel-style probing inside traffic | ❌ TBD |
| Search: per-column memory steering the probes (+ burstiness) | 🟡 past stats (last 10 SCs) feed FIX 4/5/8 only |
| Search: real-goodput objective | 🟡 measured SR × expected tpt; no MAC/retry cost |
| Protect: GPR in retry slots 3–4 | ✅ (FIX 4) |
| Protect: step-down table + continue on the good line | ✅ (FIX 6) |
| Protect: 80 ms monitor + revert | ✅ (FIX 8) |
| Protect: one time-limited probation state | ❌ TBD (FIX 8 stays armed indefinitely → −6% sudden wall) |
| Protect: direction-only guard replacing the global 1 s freeze | 🟡 FIX 2/5/7/8 bypass it for their escapes; freeze itself still there |

**TBD / open items**
- Build "TLC 2.0" as one alternative engine in the playground and run it through 🧪 Regression (proposed next step).
- Python parity for FIX 4, 5, 6, 8, 9 (only 1–3, 7 are in `tlcsim/` + `tools/replay_ab.py`).
- Run 🧪 Regression with 20 seeds and refresh `doc/tlc_fix_proposals.html` with it (the 20-seed run was cancelled; page still has 5-seed regression numbers, the FIX 7 card still says "no side effects" — it is −8% on transient OBSS, FIX 2 "risk low" is −9% there, FIX 5 is −8% at 10% collisions, and the side-effects table lacks FIX 9).
- Questions for the user / FW team: FIX 8 slide says "restore **BPR1**" — simulated as GPR1 (confirm); RTS static vs dynamic BW signalling; EHT GI code order for step-down (code 2 = 0.8 µs 4×LTF is shorter than code 1 = 1.6 µs); FW stat-window size at high rates (drives the collision-loss magnitude).
- Validate on more real logs (other 320 drops, mobility, deep fades, MIMO losses, crowded channels) — everything so far is tuned on one log.
- Git: commit `30eee03` + tag **`sysmon-replay-v1.0`** (pushed) = sysmon replay through the TVA default fix. **Everything after it is uncommitted** (FIX 4–9, RTS/CTS model, regression, proposals page, genie title, preset buttons, renumbering, handoff §13.7–13.11).
- Scratch analysis scripts (gitignored): `.claude/.temp/scratch/rts_probe.py`, `rts_dump.py`, `rts_seq.py` (RTS/CTS per BW from the sysmon), `tlc_regress.py` (Python default regression, run with `.` as arg).

---

## 14. Transcript pointer

Full uncompacted conversation transcript (for exact snippets/code):
```
c:\Users\eisack\AppData\Roaming\Code\User\workspaceStorage\33ef86635bcec206c8574fd5b0dcc230\GitHub.copilot-chat\transcripts\8d9dbd37-bb7d-4334-84b2-fda20d805af8.jsonl
```
Sessions 2026-10-12 → 10-14 (§13: sysmon replay, 320 trap, FIX 1–9):
```
c:\Users\eisack\AppData\Roaming\Code\User\workspaceStorage\efcfd5e62783e3ad73caa6af52a106ce\GitHub.copilot-chat\transcripts\f247ebf5-18c2-40d3-9d40-51962282719d.jsonl
```
