"""B4 — TLC (rate picker): pluggable interface + a compact reference implementation.

IMPORTANT: `ReferenceTLC` is a *simplified stand-in* that mirrors the real Rate Scale
Manager's decision rule (maximize Success-Ratio x throughput) and its search/dwell cadence
and thresholds. It is the SWAP POINT — to test the real firmware TLC, implement the same
`TLC` interface (configure / on_stats) around it and pass it to run_sim().
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from .rates import Rate, expected_tpt, MAX_MCS, BANDWIDTHS
from .emulator import WindowStats


@dataclass
class LinkQuality:
    """B4 output: retry table + how many frames until the next statistics report."""
    rate_table: List[Rate]
    stat_threshold: int   # frames until next report -> small = search, large = dwell

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

    def configure(self, cfg: TLCConfig) -> LinkQuality:
        self.cfg = cfg
        self.bws = [b for b in BANDWIDTHS if b <= cfg.max_bw]
        self.nss_opts = [1, 2] if cfg.max_nss >= 2 else [1]
        self.col = (1, self.bws[0], True)      # (nss, bw, gi08): start SISO, narrow, short GI
        self.mcs = 0
        self.sr: Dict = {}                     # EWMA Success Ratio per (col, mcs)
        self.state = "STAY"; self.mode = "search"
        self.succ = 0; self.fail = 0           # totalFramesSuccess / totalFramesFailed
        self.last_search_end_ms = -1e9         # time the last search cycle ended
        self.last_reason = None                # 'SUCCESS' | 'FAIL' of the previous cycle
        self.pending_reason = None             # reason of the cycle currently running
        self.search_q: List = []               # remaining candidate columns this cycle
        self.best = None                       # (col, mcs, avg_tpt) best seen this cycle
        return self._lq()

    # --- helpers ---
    def _rate(self, col=None, mcs=None) -> Rate:
        n, b, g = col if col is not None else self.col
        return Rate(self.mcs if mcs is None else mcs, n, b, g)

    def _avgtpt(self, col, mcs, sr) -> float:
        return sr * expected_tpt(self._rate(col, mcs))

    def _neighbours(self) -> List:
        """Candidate columns to try in a search cycle."""
        n, b, g = self.col
        out = []
        for nn in self.nss_opts:                        # toggle SISO / MIMO
            if nn != n:
                out.append((nn, b, g))
        i = self.bws.index(b)
        if i + 1 < len(self.bws):
            out.append((n, self.bws[i + 1], g))         # wider bandwidth
        if i - 1 >= 0:
            out.append((n, self.bws[i - 1], g))         # narrower bandwidth
        out.append((n, b, not g))                       # toggle guard interval
        return out

    def _retry_table(self) -> List[Rate]:
        table = [self._rate()]
        for d in (1, 2, 3):
            if self.mcs - d >= 0:
                table.append(self._rate(mcs=self.mcs - d))
        table.append(Rate(0, 1, 20, False))             # legacy fallback
        return table

    def _lq(self) -> LinkQuality:
        thold = self.THOLD_DWELL if self.mode == "dwell" else self.THOLD_SEARCH
        return LinkQuality(self._retry_table(), thold)

    def _enter_search(self, sr) -> None:
        self.best = (self.col, self.mcs, self._avgtpt(self.col, self.mcs, sr))
        self.search_q = self._neighbours()
        self.succ = self.fail = 0
        self.state = "SEARCH"; self.mode = "search"
        self.col = self.search_q.pop(0)                 # try the first candidate column
        self.mcs = min(self.mcs, self.cfg.max_mcs)      # same MCS = fair comparison point

    def on_stats(self, stats: WindowStats, t_ms: float) -> LinkQuality:
        key = (self.col, self.mcs)
        sr = self.EWMA_ALPHA * stats.sr + (1 - self.EWMA_ALPHA) * self.sr.get(key, stats.sr)
        self.sr[key] = sr
        self.succ += stats.acked
        self.fail += stats.txed - stats.acked

        if self.state == "STAY":
            held = False
            if sr < self.SR_FORCE or (sr < self.SR_NO_DEC and self.mcs > 0):
                self.mcs -= 1                            # down-scale within column
            elif sr >= self.SR_PERFECT and self.mcs < self.cfg.max_mcs:
                self.mcs += 1                            # up-scale within column
            else:
                held = True
            self.mode = "dwell" if held else "search"
            # real firmware trigger (_rsMngShouldStartSearchCycle):
            reason = None
            if self.succ > self.SUCCESS_LIMIT:
                if self.last_reason == "FAIL":                       # after a fail cycle: re-probe now
                    reason = "SUCCESS"
                elif (t_ms - self.last_search_end_ms) > self.SEARCH_TIME_GUARD_MS:
                    reason = "SUCCESS"                               # else guard ~300 ms
            if reason is None and self.fail > self.FAIL_LIMIT:
                reason = "FAIL"                                      # failures: no time guard
            if reason is not None:
                self.pending_reason = reason
                self._enter_search(sr)
        else:  # SEARCH — score this candidate column, then try the next
            cand = self._avgtpt(self.col, self.mcs, sr)
            if cand > self.best[2]:
                self.best = (self.col, self.mcs, cand)
            if self.search_q:
                self.col = self.search_q.pop(0)
                self.mcs = min(self.mcs, self.cfg.max_mcs)
                self.mode = "search"
            else:                                        # cycle done -> best column, settle
                self.col, self.mcs, _ = self.best
                self.state = "STAY"; self.succ = self.fail = 0
                self.last_reason = self.pending_reason   # remember why this cycle ran
                self.last_search_end_ms = t_ms
                self.mode = "dwell"
        return self._lq()
