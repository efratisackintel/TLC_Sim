"""B4 — TLC (rate picker): pluggable interface + a compact reference implementation.

IMPORTANT: `ReferenceTLC` is a *simplified stand-in* that mirrors the real Rate Scale
Manager's decision rule (maximize Success-Ratio x throughput) and its search/dwell cadence
and thresholds. It is the SWAP POINT — to test the real firmware TLC, implement the same
`TLC` interface (configure / on_stats) around it and pass it to run_sim().
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from .rates import Rate, expected_tpt, MAX_MCS, BANDWIDTHS
from .emulator import WindowStats


@dataclass
class LinkQuality:
    """B4 output: retry table + how many frames until the next statistics report."""
    rate_table: List[Rate]
    stat_threshold: int   # frames until next report -> small = search, large = dwell
    stable: Optional[Rate] = None   # FW: retry fallbacks are built from the stable column

    @property
    def primary(self) -> Rate:
        return self.rate_table[0]


@dataclass
class TLCConfig:
    """Station capabilities (the envelope the TLC works within)."""
    max_bw: int = 160
    max_nss: int = 2
    max_mcs: int = MAX_MCS


class TLC:
    """Interface every TLC implementation must provide."""
    mode: str = "-"

    def configure(self, cfg: TLCConfig) -> LinkQuality:
        raise NotImplementedError

    def on_stats(self, stats: WindowStats, t_ms: float) -> LinkQuality:
        raise NotImplementedError


class ReferenceTLC(TLC):
    """Column-based reference (closer to the real Rate Scale Manager).

    A 'column' = a fixed (NSS, BW, GI) combination; MCS is scaled inside it.
      STAY   — scale MCS up/down within the current column based on Success Ratio.
      SEARCH — periodically try neighbouring columns (toggle SISO/MIMO, ±BW, toggle GI)
               and keep the one with the best SR x expected_tpt.
    Still a model (no TPC / A-MSDU / exact firmware tables); remains the swap point for the
    real TLC.
    """
    SR_PERFECT = 0.95        # RS_MNG_PERFECT_SR
    SR_NO_DEC = 0.90         # RS_MNG_SR_NO_DECREASE
    SR_FORCE = 0.15          # RS_MNG_SR_FORCE_DECREASE
    THOLD_SEARCH = 20        # RS_STAT_THOLD (short windows)
    THOLD_DWELL = 2000       # RS_MNG_OPTIMAL_RATE_FRAME_COUNT (long windows)
    EWMA_ALPHA = 0.4
    SUCCESS_LIMIT = 4500     # RS_MNG_NON_LEGACY_SUCCESS_LIMIT (success frames)
    FAIL_LIMIT = 400         # RS_MNG_NON_LEGACY_FAILURE_LIMIT (failure frames)
    SEARCH_TIME_GUARD_MS = 300   # RS_MNG_UPSCALE_SEARCH_CYCLE_MAX_FREQ (success time guard)
    UPSCALE_GUARD_MS = 200   # RS_MNG_UPSCALE_MAX_FREQUENCY (fw mode)
    AVOID_SR = 0.70          # RS_MNG_IGNORE_HIGHER_MCS_THRESHOLD_SR
    AVOID_MS = 1000          # RS_MNG_UPSCALE_IGNORE_HIGHER_MCS
    FLOOR_SR = 0.50          # FIX 2 trigger
    STALE_MS = 300           # fw: older window stats are reset, not averaged (as the playground)
    fw = wide_confirm = floor_escape = wide_backoff = False
    init_rate: Optional[Rate] = None

    def __init__(self, fw: bool = False, wide_confirm: bool = False, floor_escape: bool = False,
                 wide_backoff: bool = False, init_rate: Optional[Rate] = None):
        """Mirrors the playground's makeTLC opts. All default off here (the playground always runs with fw on;
        this simpler TLC is only validated with fw on for Monte-Carlo trace replays, see tools/replay_ab.py).

        fw           — FW-exact details: avoid-higher-MCS (rateScaleMng.c ~L5593/L3932/L1901: after a
                       window drops from >=95% to <70% SR, block upscale AND search cycles for 1 s),
                       200 ms upscale guard, search target = measured tpt when SR <= 90% (else expected)
                       and each probe uses the lowest MCS of the column that beats it.
        wide_confirm — FIX 1: a wider-BW test column must pass 3 consecutive test windows.
        floor_escape — FIX 2: at MCS 0 with SR < 50% search at once (ignores avoid), never wider.
        wide_backoff — FIX 3: a wider BW abandoned < 3 s after commit is barred 2 s, doubling to 16 s.
        init_rate    — warm start (FW _rsMngSetInitRate); default SISO / narrowest BW / MCS 0."""
        self.fw, self.wide_confirm = fw, wide_confirm
        self.floor_escape, self.wide_backoff = floor_escape, wide_backoff
        self.init_rate = init_rate

    def configure(self, cfg: TLCConfig) -> LinkQuality:
        self.cfg = cfg
        self.bws = [b for b in BANDWIDTHS if b <= cfg.max_bw]
        self.nss_opts = [1, 2] if cfg.max_nss >= 2 else [1]
        self.col = (1, self.bws[0], True)      # (nss, bw, gi08): start SISO, narrow, short GI
        self.mcs = 0
        if getattr(self, "init_rate", None) is not None:
            r = self.init_rate
            self.col, self.mcs = (r.nss, r.bw, r.gi08), r.mcs
        self.sr: Dict = {}                     # EWMA Success Ratio per (col, mcs)
        self.sr_t: Dict = {}                   # last update time per (col, mcs)
        self.state = "STAY"; self.mode = "search"
        self.succ = 0; self.fail = 0           # totalFramesSuccess / totalFramesFailed
        self.last_search_end_ms = -1e9         # time the last search cycle ended
        self.last_reason = None                # 'SUCCESS' | 'FAIL' | 'FLOOR' of the previous cycle
        self.pending_reason = None             # reason of the cycle currently running
        self.search_q: List = []               # remaining candidate columns this cycle
        self.best = None                       # (col, mcs, avg_tpt) best seen this cycle
        self.stable_col = self.col             # stable column the search reverts/falls back to
        self.stable_mcs = self.mcs
        self.target = 0.0                      # fw: search target tpt
        self.avoid_hi = False; self.avoid_t = -1e9
        self.next_up = -1e9
        self.conf = 0
        self.ban: Dict[int, float] = {}; self.backoff: Dict[int, float] = {}
        self.wide_since = None                 # (bw, t) of the last wider-BW commit
        self.sc_log: List[dict] = []           # one dict per search cycle (incl. blocked ones)
        self.cur_sc = None
        return self._lq()

    # --- helpers ---
    def _rate(self, col=None, mcs=None) -> Rate:
        n, b, g = col if col is not None else self.col
        return Rate(self.mcs if mcs is None else mcs, n, b, g)

    def _avgtpt(self, col, mcs, sr) -> float:
        return sr * expected_tpt(self._rate(col, mcs))

    def _neighbours(self, t_ms: float = 0.0, no_wider: bool = False) -> List:
        """Candidate columns to try in a search cycle."""
        n, b, g = self.col
        out = []
        for nn in self.nss_opts:                        # toggle SISO / MIMO
            if nn != n:
                out.append((nn, b, g))
        i = self.bws.index(b)
        if i + 1 < len(self.bws) and not no_wider \
                and not (self.wide_backoff and self.ban.get(self.bws[i + 1], -1e9) > t_ms):
            out.append((n, self.bws[i + 1], g))         # wider bandwidth
        if i - 1 >= 0:
            out.append((n, self.bws[i - 1], g))         # narrower bandwidth
        out.append((n, b, not g))                       # toggle guard interval
        return out

    def _probe_mcs(self, col) -> int:
        if not self.fw:
            return min(self.mcs, self.cfg.max_mcs)      # same MCS = fair comparison point
        for m in range(self.cfg.max_mcs + 1):           # FW _rsMngGetBestRate: lowest MCS beating target
            if expected_tpt(self._rate(col, m)) >= self.target:
                return m
        return self.cfg.max_mcs

    def _retry_table(self) -> List[Rate]:
        table = [self._rate()]
        for d in (1, 2, 3):
            if self.mcs - d >= 0:
                table.append(self._rate(mcs=self.mcs - d))
        table.append(Rate(0, 1, 20, False))             # legacy fallback
        return table

    def _lq(self) -> LinkQuality:
        thold = self.THOLD_DWELL if self.mode == "dwell" else self.THOLD_SEARCH
        if self.state == "SEARCH":
            n, b, g = self.stable_col
            stable = Rate(self.stable_mcs, n, b, g)
        else:
            stable = self._rate()
        return LinkQuality(self._retry_table(), thold, stable)

    def _enter_search(self, sr, t_ms: float = 0.0) -> None:
        self.stable_col = self.col              # remember the stable column before probing (FW fallback base)
        self.stable_mcs = self.mcs
        inc = self._avgtpt(self.col, self.mcs, sr)
        self.best = (self.col, self.mcs, inc)
        if self.fw:   # FW _rsMngSearchBetterCol: SR <= 90% -> target = measured tpt, else expected
            self.target = expected_tpt(self._rate()) if sr > self.SR_NO_DEC else inc
        self.cur_sc = {"t_ms": t_ms, "reason": self.pending_reason, "from": self._rate(),
                       "to": None, "probes": [], "blocked": False}
        self.sc_log.append(self.cur_sc)
        self.search_q = self._neighbours(t_ms, self.pending_reason == "FLOOR")
        self.succ = self.fail = 0
        self.state = "SEARCH"; self.mode = "search"; self.conf = 0
        self.col = self.search_q.pop(0)                 # try the first candidate column
        self.mcs = self._probe_mcs(self.col)

    def _commit(self, t_ms: float) -> None:
        """Search cycle done -> best column, settle (and track wider-BW commits for FIX 3)."""
        frm = self.stable_col
        self.col, self.mcs, _ = self.best
        self.state = "STAY"; self.succ = self.fail = 0
        self.last_reason = self.pending_reason   # remember why this cycle ran
        self.last_search_end_ms = t_ms
        self.mode = "dwell"
        if self.col[1] > frm[1]:
            self.wide_since = (self.col[1], t_ms)
        elif self.wide_since and self.col[1] < self.wide_since[0]:
            b, t0 = self.wide_since
            if t_ms - t0 < 3000:
                self.backoff[b] = min(16000, (self.backoff.get(b) or 1000) * 2)
                self.ban[b] = t_ms + self.backoff[b]
            else:
                self.backoff[b] = 0
            self.wide_since = None
        if self.cur_sc is not None:
            self.cur_sc["to"] = self._rate()
            self.cur_sc = None

    def on_stats(self, stats: WindowStats, t_ms: float) -> LinkQuality:
        key = (self.col, self.mcs)
        prev = self.sr.get(key)
        if self.fw and t_ms - self.sr_t.get(key, -1e9) > self.STALE_MS:
            sr = stats.sr                               # stale/new window (FW clears the test column's window)
        else:
            sr = self.EWMA_ALPHA * stats.sr + (1 - self.EWMA_ALPHA) * self.sr.get(key, stats.sr)
        self.sr[key] = sr
        self.sr_t[key] = t_ms
        if self.fw:
            if prev is not None and prev >= self.SR_PERFECT and sr < self.AVOID_SR:
                self.avoid_hi, self.avoid_t = True, t_ms
            elif self.avoid_hi and t_ms - self.avoid_t > self.AVOID_MS:
                self.avoid_hi = False
        self.succ += stats.acked
        self.fail += stats.txed - stats.acked

        if self.state == "STAY":
            held = False
            if sr < self.SR_FORCE or (sr < self.SR_NO_DEC and self.mcs > 0):
                if self.mcs > 0:
                    self.mcs -= 1                        # down-scale within column
            elif sr >= self.SR_PERFECT and self.mcs < self.cfg.max_mcs:
                if self.fw and (self.avoid_hi or t_ms < self.next_up):
                    held = True
                else:
                    self.mcs += 1                        # up-scale within column
                    self.next_up = t_ms + self.UPSCALE_GUARD_MS
            else:
                held = True
            self.mode = "dwell" if held else "search"
            # real firmware trigger (_rsMngShouldStartSearchCycle):
            reason = None
            if self.succ > self.SUCCESS_LIMIT:
                if self.last_reason in ("FAIL", "FLOOR"):           # after a fail cycle: re-probe now
                    reason = "SUCCESS"
                elif (t_ms - self.last_search_end_ms) > self.SEARCH_TIME_GUARD_MS:
                    reason = "SUCCESS"                               # else guard ~300 ms
            if reason is None and self.fail > self.FAIL_LIMIT:
                reason = "FAIL"                                      # failures: no time guard
            floor = (self.floor_escape and self.mcs == 0 and sr < self.FLOOR_SR
                     and self.col[1] > self.bws[0]
                     and t_ms - self.last_search_end_ms > self.UPSCALE_GUARD_MS)
            if floor:
                reason = "FLOOR"
            if reason is not None and self.avoid_hi and not floor:
                # FW: _rsMngSearchBetterCol returns FALSE -> the cycle starts and ends at once
                self.sc_log.append({"t_ms": t_ms, "reason": reason, "from": self._rate(),
                                    "to": self._rate(), "probes": [], "blocked": True})
                self.succ = self.fail = 0
                self.last_reason = reason
                self.last_search_end_ms = t_ms
            elif reason is not None:
                self.pending_reason = reason
                self._enter_search(sr, t_ms)
        else:  # SEARCH — score this candidate column, then try the next
            cand = self._avgtpt(self.col, self.mcs, sr)
            if self.cur_sc is not None:
                self.cur_sc["probes"].append((self._rate(), round(cand, 1), round(sr, 2)))
            if self.wide_confirm and self.col[1] > self.stable_col[1]:
                c = self._avgtpt(self.col, self.mcs, stats.sr)   # raw test window, no EWMA carry-over
                if c > self.best[2]:
                    self.conf += 1
                    if self.conf < 3:
                        self.mode = "search"
                        return self._lq()                        # re-test the same wider column
                    self.best = (self.col, self.mcs, c)
                self.conf = 0
            elif cand > self.best[2]:
                self.best = (self.col, self.mcs, cand)
            if self.fw and self.avoid_hi and self.pending_reason != "FLOOR":
                self.search_q = []                               # FW: no more columns while avoid is set
            if self.search_q:
                self.col = self.search_q.pop(0)
                self.mcs = self._probe_mcs(self.col)
                self.mode = "search"
            else:
                self._commit(t_ms)
        return self._lq()
