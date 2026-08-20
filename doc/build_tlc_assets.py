#!/usr/bin/env python3
"""Generate diagrams (PNG) for the TLC Word document using matplotlib."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)

BLUE = "#0071C5"
DARK = "#1F2A44"
LIGHT = "#EAF3FB"
GREEN = "#2E8B57"
ORANGE = "#E8820C"
GREY = "#8A94A6"


def _box(ax, x, y, w, h, text, fc=LIGHT, ec=BLUE, tc=DARK, fs=11, bold=True):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                         linewidth=1.8, edgecolor=ec, facecolor=fc, mutation_aspect=1)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, fontweight="bold" if bold else "normal", wrap=True)


def _arrow(ax, x1, y1, x2, y2, color=BLUE, text=None, tx=None, ty=None, style="-|>", lw=1.8, rad=0.0):
    ar = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                         linewidth=lw, color=color,
                         connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(ar)
    if text:
        ax.text(tx if tx is not None else (x1 + x2) / 2,
                ty if ty is not None else (y1 + y2) / 2,
                text, ha="center", va="center", fontsize=8.5, color=color,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


def hierarchy():
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    layers = [
        (8.0, "HOST / DRIVER\nMmacLinkQuality \u2022 DataPathTlcConfig", LIGHT, BLUE),
        (5.7, "UPPER MAC (UMAC)  \u2014  the 'brain'\nrateScaleMng \u2022 rateScaleAggMng", "#DCEDFB", BLUE),
        (3.4, "LOWER MAC (LMAC)\nrateScale (apply) \u2022 tlc (statistics)", "#E7F5EC", GREEN),
        (1.1, "PHY / HARDWARE\nrate_n_flags \u2192 PHY vector", "#FBEFE0", ORANGE),
    ]
    for y, txt, fc, ec in layers:
        _box(ax, 1.6, y, 6.8, 1.7, txt, fc=fc, ec=ec, fs=11)
    # down arrows (left) - config / retry table
    _arrow(ax, 3.2, 8.0, 3.2, 7.4, BLUE, "TLC_MNG_CONFIG_CMD", 3.2, 7.7)
    _arrow(ax, 3.2, 5.7, 3.2, 5.1, BLUE, "LINK_QUALITY_CMD\n(retry table)", 3.2, 5.4)
    _arrow(ax, 3.2, 3.4, 3.2, 2.8, GREEN, "apply per-frame rate", 3.2, 3.1)
    # up arrows (right) - stats / notif
    _arrow(ax, 6.8, 2.8, 6.8, 3.4, ORANGE, "TX status\n(txed/acked/BA)", 6.8, 3.1)
    _arrow(ax, 6.8, 5.1, 6.8, 5.7, GREEN, "TLC_STAT_NTFY\n(success ratio)", 6.8, 5.4)
    _arrow(ax, 6.8, 7.4, 6.8, 8.0, BLUE, "TLC_MNG_UPDATE_NTFY", 6.8, 7.7)
    ax.text(5, 9.8, "TLC Layered Hierarchy & Data Flow", ha="center", fontsize=13,
            fontweight="bold", color=DARK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "hierarchy.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def feedback():
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis("off")
    nodes = [
        (0.3, "HW TX\n+ BA", "#FBEFE0", ORANGE),
        (3.1, "LMAC tlc\ncollect stats", "#E7F5EC", GREEN),
        (5.9, "UMAC rateScaleMng\nSR, avgTPT, decision", "#DCEDFB", BLUE),
        (8.7, "LMAC rateScale\napply retry table", "#E7F5EC", GREEN),
    ]
    for x, txt, fc, ec in nodes:
        _box(ax, x, 1.8, 2.5, 1.6, txt, fc=fc, ec=ec, fs=9.5)
    _arrow(ax, 2.8, 2.6, 3.1, 2.6, GREEN)
    _arrow(ax, 5.6, 2.6, 5.9, 2.6, BLUE)
    _arrow(ax, 8.4, 2.6, 8.7, 2.6, GREEN)
    # loop back
    _arrow(ax, 9.95, 1.8, 1.55, 1.2, GREY, "next TX uses new rate", 5.7, 0.7, rad=-0.25)
    _arrow(ax, 1.55, 1.8, 1.55, 1.8, GREY)
    ax.text(6, 4.6, "Closed-Loop Rate Adaptation", ha="center", fontsize=12.5,
            fontweight="bold", color=DARK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "feedback.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def state_machine():
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis("off")
    _box(ax, 0.6, 1.9, 3.0, 1.4, "STAY_IN_COLUMN\nsteady rate", "#DCEDFB", BLUE, fs=10)
    _box(ax, 4.5, 1.9, 3.0, 1.4, "SEARCH_CYCLE\nprobe columns/BW", "#E7F5EC", GREEN, fs=10)
    _box(ax, 8.4, 1.9, 3.0, 1.4, "TPC_SEARCH\nreduce power", "#FBEFE0", ORANGE, fs=10)
    _arrow(ax, 3.6, 2.9, 4.5, 2.9, BLUE, "succ/fail/time", 4.05, 3.35)
    _arrow(ax, 4.5, 2.3, 3.6, 2.3, GREEN, "better / none", 4.05, 1.7, rad=0.0)
    _arrow(ax, 7.5, 2.6, 8.4, 2.6, GREEN, "optimal rate", 7.95, 3.05)
    _arrow(ax, 9.9, 1.9, 2.1, 1.9, ORANGE, "power done \u2192 back to steady", 6.0, 0.75, rad=0.28)
    ax.text(6, 4.6, "Rate-Scale State Machine", ha="center", fontsize=12.5,
            fontweight="bold", color=DARK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "state.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def retry_ladder():
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    rows = [
        ("Idx 0-2  Primary rate (best MCS)", 8.6, BLUE, 9.2),
        ("Idx 3-4  Secondary  (MCS \u2212 1)", 7.2, "#2C82C9", 8.0),
        ("Idx 5    Tertiary   (MCS \u2212 2)", 5.8, GREEN, 6.8),
        ("Idx 6-12 Fallbacks  (SISO / other GI)", 4.4, ORANGE, 5.4),
        ("Idx 13-15 Legacy    (OFDM / CCK)", 3.0, "#C0392B", 4.0),
    ]
    for txt, y, color, w in rows:
        _box(ax, 0.6, y, w, 1.05, txt, fc="white", ec=color, tc=color, fs=10)
    _arrow(ax, 9.4, 9.1, 9.4, 3.5, GREY, "used only if\nprevious\nrates fail", 9.9, 6.3)
    ax.text(5, 9.9, "Retry Table (rate_scale_table[])", ha="center", fontsize=12.5,
            fontweight="bold", color=DARK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "retry.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def tpt_chart():
    # HE 80 MHz, GI 0.8us, SISO vs MIMO (Mbps = value/10)
    mcs = list(range(0, 12))
    siso = [306, 612, 918, 1225, 1837, 2450, 2756, 3062, 3675, 4083, 4593, 5104]
    mimo = [612, 1225, 1837, 2450, 3675, 4900, 5512, 6125, 7350, 8166, 9187, 10208]
    siso = [v / 10 for v in siso]
    mimo = [v / 10 for v in mimo]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    w = 0.4
    x = range(len(mcs))
    ax.bar([i - w / 2 for i in x], siso, width=w, label="SISO (1 stream)", color=BLUE)
    ax.bar([i + w / 2 for i in x], mimo, width=w, label="MIMO (2 streams)", color=GREEN)
    ax.set_xticks(list(x)); ax.set_xticklabels([f"MCS{m}" for m in mcs], fontsize=8)
    ax.set_ylabel("Expected throughput (Mbps)", fontsize=10)
    ax.set_title("Expected Throughput \u2014 HE, 80 MHz, GI 0.8 \u00b5s", fontsize=12.5,
                 fontweight="bold", color=DARK)
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "tpt_chart.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    hierarchy(); feedback(); state_machine(); retry_ladder(); tpt_chart()
    print("assets written to", ASSETS)


if __name__ == "__main__":
    main()
