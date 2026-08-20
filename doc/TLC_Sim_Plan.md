# TLC Simulation Harness — Implementation Plan (Draft)

> Goal: a **small, efficient** closed-loop bench to test the **real** TLC (Rate Scale
> Manager) code **unchanged**, by feeding it channel-driven statistics and recording how it
> adapts. Both time regimes must be exercised: the **search-cycle period** (fast probing) and
> the **functional / dwell period** (~500 ms stay on the chosen rate).
> Companion diagram: `doc/tlc_sim_architecture.html`.

---

## 1. Guiding principles

- **B4 = the current firmware `rateScaleMng`, as-is** — compiled and driven through its real
  interfaces, **not** reimplemented.
- **Reuse the existing USFSTL software-testing infra** (`fw/tests/softwareTesting`). It already
  compiles UMAC, injects TLC statistics, and captures the Link-Quality output
  (`usimLibLmacTlc`). The harness is an extension of the existing `umacSimTlc` test flow.
- **Keep the MVP minimal**: single station, coarse PER (formula), one scenario, CSV log.
- Everything advanced (Monte-Carlo, calibrated tables, multi-station, plots) is **Phase 2+**.

---

## 2. Blocks (B1–B6): reuse vs. add

| Block | What it is | Reuse / Add |
|-------|-----------|-------------|
| **B4 · TLC** | Real `rateScaleMng` (Rate Scale Manager) | **Reuse, unchanged** |
| **B5 · State + History** | Real `RS_MNG_STA_INFO_S` (TLC's own memory) + thin run-log | Reuse struct; **add** small log |
| **B3 · TX/Stats Emulator** | Turns rate table + channel into `txed/acked` and pushes the stat notification | **Extend** `usimLibLmacTlc` stat generation |
| **B2 · PER Model** | Pure `per(rate, channel) → PER` (+ expected tpt) | **Add** small module |
| **B1 · Channel Config** | `channelState(t) = {SNR/quality, collision}` over time | **Add** small scenario |
| **B6 · Harness/Scheduler** | Clock, window sizing (search vs dwell), loop, logging, KPIs | **Add** driver (like an extended UTest) |

---

## 3. How B4 (real TLC) is driven (its actual entry points)

- **Config in:** `TLC_MNG_CONFIG` → `cmdHandlerTlcConfigInUmac` (station capabilities).
- **Statistics in:** the `TLC_STAT_NTFY` path → `tlcStatUpdateHandler` (txed, acked, BA → SR).
- **Rate table out:** `STATION_TX_LINK_QUALITY_S` (`LINK_QUALITY_CMD`) via
  `rxtxStaInfoHandleTxLinkQuality` — already captured by `usimLibLmacTlcWaitForLqCmd`.
- **Update notif (optional):** `TLC_MNG_UPDATE_NTFY` (rate, A-MSDU).
- **Rate encoding:** `RATE_MCS_API_U` (`rate_n_flags`).

No change to any TLC source — the harness only calls these interfaces and captures the output.

---

## 4. The two time regimes (core requirement)

The regimes are **not hardcoded** — they emerge from the **stat-report threshold that the TLC
itself requests** (exactly as in the real `TLC_CONFIG`):

| Regime | TLC stat threshold | Harness behavior | TLC guards active |
|--------|--------------------|------------------|-------------------|
| **Search-cycle period** | ~20 frames (`RS_STAT_THOLD`) | many **short** windows → frequent SR reports so TLC can compare rates/columns | upscale ≥ 200 ms, search ≥ 300 ms |
| **Functional / dwell period** | ~2000 frames (`RS_MNG_OPTIMAL_RATE_FRAME_COUNT`) | few **long** windows → sparse SR reports; PR + retry table held | ~500 ms TPC / A-MSDU enable timers |

**B6 reads the threshold the TLC asks for and sizes the next window accordingly.** This is what
makes the search→stay behavior appear naturally.

---

## 5. Simulated clock (so TLC timers work)

TLC reads system time (`systemTimeGet`) for its 200 / 300 / 500 ms logic, so the harness must
own a **controllable clock**:

- Per window: `elapsed = frames_in_window × airtime_per_frame(current primary rate)`.
- `airtime_per_frame ≈ frame_bytes × 8 / phyRate(rate)`; `phyRate` from the expected-tpt tables.
- B6 advances the sim clock by `elapsed` before the next window.
- **MVP simplification:** coarse airtime from the Mbps tables is enough to make the
  200/300/500 ms timers fire at the right cadence.

---

## 6. Per-window loop (one control-loop iteration)

1. **B6** sets `windowFrames` = the stat threshold the TLC currently requests.
2. **B1** → `channelState(t)` = {SNR/quality, collision}.
3. **B3** applies the captured rate table for the window:
   - *Coarse (MVP):* use the **primary rate** only → `acked ≈ txed × (1 − PER_primary)`.
   - *Realistic (Phase 2):* walk the **retry chain**, call `B2.per(rate, channel)` per rate,
     draw success/fail, model A-MPDU/Block-ACK; accumulate `txed/acked` per rate.
4. **B3** pushes the statistics via the real stat path → **B4** processes, updates **B5**, and
   may emit a **new rate table** (B6 captures it).
5. **B6** advances the clock by the window's airtime; **logs** `{t, primaryRate, SR, tpt,
   state, threshold}`.
6. Repeat.

---

## 7. PER model (B2) — MVP then Phase 2

- **MVP (formula):** `SR = sigmoid(quality − requiredQuality(rate))`, `PER = 1 − SR`, then apply
  collision. Reuse the exact curve + expected-tpt tables already used in `tlc_playground.html`.
  Decomposition: `P_success = P_link(rate,SNR) × (1 − P_collision)`.
- **Phase 2:** calibrated PER-vs-SNR tables per (MCS, BW, NSS); optional per-frame Monte-Carlo
  draws for realistic variance.

---

## 8. Files (add small, reuse big)

**Reuse:** `fw/tests/softwareTesting` (USFSTL), `rateScaleMng.*`, `usimLibLmacTlc.*`,
expected-tpt tables.

**Add (small, indicative names):**
- `perModel.{c,h}` — B2
- `channelScenario.{c,h}` — B1 (time-scripted channel)
- `tlcSimHarness.{c,h}` — B6 loop + simulated clock + logger + KPIs
- a scenario definition (channel vs time) + CSV output

---

## 9. Phased delivery

- **Phase 1 (MVP):** single station · coarse PER (formula) · one ramp/step scenario ·
  CSV log of `rate/SR/tpt/state` · demonstrably exercises **search → stay → re-search**.
- **Phase 2:** full retry-chain + A-MPDU in B3 · calibrated PER tables + Monte-Carlo ·
  more scenarios · KPI summary · A/B compare of TLC variants.
- **Phase 3 (optional):** multi-station · BT/SAR/thermal inputs · plots/dashboards.

---

## 10. KPIs (scoring a TLC run)

- Average throughput; throughput vs. theoretical max (**efficiency**)
- Success-Ratio stability (variance)
- **Reaction time** to a channel change
- Number of rate switches; **% time on the optimal rate**

---

## 11. Decisions (defaults picked for simplicity)

| Decision | Default | Why |
|----------|---------|-----|
| Platform | **C on USFSTL** | forced by "use the real TLC as-is" |
| PER model | **formula first**, tables later | fastest to stand up |
| Emulator fidelity | **coarse first** (primary rate) | MVP; retry-chain in Phase 2 |
| Scope | **single station** first | simplicity |
| Tick | **one stat window** (variable size, TLC-driven) | gives search vs dwell for free |

---

## 12. Open questions for you

1. OK to build on the existing `umacSimTlc` / USFSTL flow (C), given the "real TLC as-is" goal?
2. First scenario to model (e.g., SNR ramp down then up; sudden step; steady + interference burst)?
3. Output format — CSV only for MVP, or also a small plot later?

_Status: planning draft. No code written yet._
