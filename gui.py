"""GUI to run the TLC simulation, configure the scenario, and plot:
  1) TLC decision (MCS) vs time     2) Throughput vs time     3) PER vs time

Run:  python gui.py     (needs matplotlib; tkinter ships with Python)
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from tlcsim import run_sim, ReferenceTLC, TLCConfig, Channel, Seg

# ── scenario presets: lines of  "ms, snr_db[, snr_end[, collision]]" ──
PRESETS = {
    "fade & recover": "3000, 40\n3000, 40, 6\n3000, 6, 40",
    "sudden drop":    "3000, 40\n3000, 8\n3000, 40",
    "interference burst": "2000, 35, -, 0.02\n2000, 35, -, 0.40\n2000, 35, -, 0.02",
    "steady":         "6000, 32, -, 0.05",
    "long fade":      "2000, 45\n5000, 45, 2\n2000, 2, 45",
}


def parse_segments(text: str):
    """Parse the scenario text box into a list of Seg."""
    segs = []
    for ln, line in enumerate(text.strip().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.replace(";", ",").split(",")]
        if len(parts) < 2:
            raise ValueError(f"line {ln}: need at least 'ms, snr_db'")
        ms = float(parts[0]); snr_db = float(parts[1])
        se = None
        if len(parts) > 2 and parts[2] not in ("", "-"):
            se = float(parts[2])
        col = float(parts[3]) if len(parts) > 3 and parts[3] not in ("", "-") else 0.0
        segs.append(Seg(ms=ms, snr_db=snr_db, snr_end=se, collision=col))
    if not segs:
        raise ValueError("no segments defined")
    return segs


def _spans(recs, value, attr="mode"):
    """Merge contiguous records where getattr(r, attr) == value into (t0, t1) second-spans."""
    spans, start = [], None
    for r in recs:
        if getattr(r, attr) == value and start is None:
            start = r.t_ms
        elif getattr(r, attr) != value and start is not None:
            spans.append((start / 1000, r.t_ms / 1000)); start = None
    if start is not None:
        spans.append((start / 1000, recs[-1].t_ms / 1000))
    return spans


class App:
    def __init__(self, root: tk.Tk):
        root.title("TLC Simulation — scenario & plots")
        root.geometry("1180x760")

        # ---- left: controls ----
        left = ttk.Frame(root, padding=10); left.pack(side="left", fill="y")

        ttk.Label(left, text="Scenario preset").pack(anchor="w")
        self.preset = ttk.Combobox(left, values=list(PRESETS), state="readonly", width=24)
        self.preset.set("fade & recover"); self.preset.pack(anchor="w", pady=(0, 6))
        self.preset.bind("<<ComboboxSelected>>", self._load_preset)

        ttk.Label(left, text="Segments:  ms, snr_db[, snr_end[, collision]]").pack(anchor="w")
        self.txt = tk.Text(left, width=34, height=12, font=("Consolas", 10))
        self.txt.pack(anchor="w"); self.txt.insert("1.0", PRESETS["fade & recover"])

        cfg = ttk.LabelFrame(left, text="TLC capabilities", padding=8)
        cfg.pack(anchor="w", fill="x", pady=8)
        ttk.Label(cfg, text="max BW").grid(row=0, column=0, sticky="w")
        self.bw = ttk.Combobox(cfg, values=[20, 40, 80, 160, 320], state="readonly", width=6)
        self.bw.set(160); self.bw.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(cfg, text="streams").grid(row=1, column=0, sticky="w")
        self.nss = ttk.Combobox(cfg, values=[1, 2], state="readonly", width=6)
        self.nss.set(2); self.nss.grid(row=1, column=1, sticky="w", padx=4)
        self.mc = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Monte-Carlo (random draws)", variable=self.mc).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        btns = ttk.Frame(left); btns.pack(anchor="w", fill="x", pady=6)
        ttk.Button(btns, text="▶ Run", command=self.run).pack(side="left")
        ttk.Button(btns, text="Save CSV", command=self.save_csv).pack(side="left", padx=6)

        self.kpi = tk.Text(left, width=34, height=9, font=("Consolas", 9), bg="#f4f8fc")
        self.kpi.pack(anchor="w", pady=(6, 0))

        # ---- right: figure ----
        right = ttk.Frame(root); right.pack(side="right", fill="both", expand=True)
        self.fig = Figure(figsize=(8, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(self.canvas, right)

        self._result = None
        self.run()

    def _load_preset(self, *_):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", PRESETS[self.preset.get()])

    def run(self):
        try:
            channel = Channel(parse_segments(self.txt.get("1.0", "end")))
            cfg = TLCConfig(max_bw=int(self.bw.get()), max_nss=int(self.nss.get()))
            res = run_sim(channel, ReferenceTLC(), cfg, monte_carlo=self.mc.get())
        except Exception as e:  # surface config errors to the user
            messagebox.showerror("Scenario error", str(e)); return
        self._result = res
        self._plot(res)
        s = res.summary()
        s["search_cycles"] = len(_spans(res.records, "SEARCH", "state"))
        self.kpi.delete("1.0", "end")
        self.kpi.insert("1.0", "\n".join(f"{k:16}: {v}" for k, v in s.items()))

    def save_csv(self):
        if not self._result:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="tlc_run.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            self._result.to_csv(path)
            messagebox.showinfo("Saved", f"Wrote {path}")

    def _plot(self, res):
        recs = res.records
        t = [r.t_ms / 1000 for r in recs]
        self.fig.clear()
        ax1, ax2, ax3 = self.fig.subplots(3, 1, sharex=True)

        # shade STAY (in a column / dwell) green; mark each SEARCH cycle with a bold amber line
        for a, b in _spans(recs, "STAY", "state"):
            ax1.axvspan(a, b, color="#2E8B57", alpha=0.08, lw=0)
        for a, b in _spans(recs, "SEARCH", "state"):
            for ax in (ax1, ax2, ax3):
                ax.axvspan(a, b, color="#E8820C", alpha=0.30, lw=0)
                ax.axvline(a, color="#E8820C", lw=1.4, alpha=0.9)

        # 1) TLC decision: MCS + channel SNR
        ax1.step(t, [r.mcs for r in recs], where="post", color="#0071C5", lw=1.6, label="MCS")
        ax1.set_ylabel("MCS"); ax1.set_ylim(-0.5, 13.5); ax1.grid(alpha=.3)
        qx = ax1.twinx()
        qx.plot(t, [r.snr_db for r in recs], color="#94a3b8", ls="--", lw=1, label="channel SNR")
        qx.set_ylabel("SNR (dB)")
        ax1.set_title("TLC decision — MCS vs time   (amber line = SEARCH cycle · green = in-column/dwell · dashed = SNR)")
        ax1.legend(handles=[Line2D([0], [0], color="#E8820C", lw=2.4, label="search cycle"),
                            Patch(facecolor="#2E8B57", alpha=0.3, label="in column (dwell)")],
                   loc="upper right", fontsize=8)

        # 2) throughput
        ax2.step(t, [r.tpt for r in recs], where="post", color="#2E8B57", lw=1.6, label="achieved")
        ax2.step(t, [r.best_tpt for r in recs], where="post", color="#b39ddb", lw=1.2, label="best possible")
        ax2.set_ylabel("Mbps"); ax2.grid(alpha=.3); ax2.legend(loc="upper right", fontsize=8)
        ax2.set_title("Throughput vs time")

        # 3) PER of the primary rate
        ax3.step(t, [max(0.0, 1 - r.sr) for r in recs], where="post", color="#C0392B", lw=1.6)
        ax3.set_ylabel("PER"); ax3.set_ylim(0, 1); ax3.grid(alpha=.3)
        ax3.set_xlabel("time (s)"); ax3.set_title("PER (primary rate) vs time")

        self.fig.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
