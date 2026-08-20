"""Render a MATLAB .fig file (MAT v5 'hgS' figure struct) with matplotlib.

MATLAB .fig files are MAT-files storing a handle-graphics object tree.
This walks that tree, pulls Line objects (XData/YData) plus axes labels,
titles, legend and log-scale, and re-plots them so the figure can be
viewed without MATLAB.

Usage:
    python fig_viewer.py "path/to/file.fig" [--save out.png]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
from scipy.io import loadmat


def _val(x):
    """Unwrap the nested 1x1 object/char arrays scipy returns for MAT structs."""
    while isinstance(x, np.ndarray) and x.dtype == object and x.size == 1:
        x = x.item()
    if isinstance(x, np.ndarray) and x.dtype.kind in ("U", "S") and x.size == 1:
        return str(x.item())
    if isinstance(x, np.ndarray) and x.dtype.kind in ("U", "S"):
        return "".join(x.astype(str).ravel())
    return x


def _prop(props, name, default=None):
    if props is None:
        return default
    try:
        fields = props.dtype.names or ()
    except AttributeError:
        return default
    if name in fields:
        return _val(props[name])
    return default


def _is_struct(x):
    return hasattr(x, "dtype") and getattr(x.dtype, "names", None)


def _node(obj):
    """Return (type, properties_struct, children_array) for a hg node."""
    obj = _val(obj)
    if isinstance(obj, np.ndarray) and obj.dtype == object and obj.size == 1:
        obj = obj.item()
    fields = obj.dtype.names or ()
    typ = str(_val(obj["type"])) if "type" in fields else ""
    props = obj["properties"] if "properties" in fields else None
    if isinstance(props, np.ndarray) and props.size == 1:
        props = props.item() if props.dtype == object else props[0, 0] if props.ndim == 2 else props.ravel()[0]
    children = obj["children"] if "children" in fields else None
    return typ, props, children


def _iter_children(children):
    if children is None:
        return
    children = np.asarray(children).ravel()
    for c in children:
        if isinstance(c, np.ndarray) and c.dtype == object and c.size == 1:
            c = c.item()
        if _is_struct(c):
            yield c


def collect_axes(node, out):
    typ, props, children = _node(node)
    if typ == "axes":
        out.append((props, children))
    for c in _iter_children(children):
        collect_axes(c, out)


def render(path: str, save: str | None = None):
    import matplotlib

    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt


    mat = loadmat(path, squeeze_me=False, struct_as_record=True)
    root_key = next((k for k in mat if k.startswith("hgS")), None)
    if root_key is None:
        raise SystemExit(f"No hgS figure struct found in {path}")

    fig_root = mat[root_key]
    axes_list: list = []
    for n in np.asarray(fig_root).ravel():
        collect_axes(n, axes_list)
    if not axes_list:
        raise SystemExit("No axes found in figure.")

    fig, mpl_axes = plt.subplots(len(axes_list), 1, squeeze=False,
                                 figsize=(9, 5 * len(axes_list)))
    for ax_idx, (props, children) in enumerate(axes_list):
        ax = mpl_axes[ax_idx][0]
        legend_labels = []
        for child in _iter_children(children):
            ctyp, cprops, _ = _node(child)
            if ctyp != "graph2d.lineseries" and ctyp != "line":
                continue
            x = np.asarray(_prop(cprops, "XData"), dtype=float).ravel()
            y = np.asarray(_prop(cprops, "YData"), dtype=float).ravel()
            if x.size == 0 or y.size == 0:
                continue
            disp = _prop(cprops, "DisplayName")
            marker = _prop(cprops, "Marker", "none")
            style = _prop(cprops, "LineStyle", "-")
            (line,) = ax.plot(
                x, y,
                marker=None if marker in (None, "none") else marker,
                linestyle="-" if style in (None, "none") else style,
                markersize=4,
            )
            if disp:
                lbl = _short(_clean(_flatten_str(disp)))
                line.set_label(lbl)
                legend_labels.append(lbl)

        xl = _prop(_prop_struct(_prop(props, "XLabel")), "String")
        yl = _prop(_prop_struct(_prop(props, "YLabel")), "String")
        tt = _prop(_prop_struct(_prop(props, "Title")), "String")
        if xl:
            ax.set_xlabel(_clean(_flatten_str(xl)))
        if yl:
            ax.set_ylabel(_clean(_flatten_str(yl)))
        if tt:
            ax.set_title(_short(_clean(_flatten_str(tt)), 90), fontsize=8)
        if str(_prop(props, "XScale", "linear")) == "log":
            ax.set_xscale("log")
        if str(_prop(props, "YScale", "linear")) == "log":
            ax.set_yscale("log")
        ax.grid(True, which="both", ls=":", alpha=0.6)
        if legend_labels:
            ax.legend(fontsize=7, loc="best")

    fig.suptitle(path.rsplit("\\", 1)[-1], fontsize=10)
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=130)
        print(f"Saved {save}")
    else:
        plt.show()


def _prop_struct(x):
    x = _val(x)
    if isinstance(x, np.ndarray) and x.dtype.names and "properties" in x.dtype.names:
        p = x["properties"]
        return p.item() if isinstance(p, np.ndarray) and p.size == 1 else p
    return x


def _flatten_str(s):
    if isinstance(s, np.ndarray):
        return " ".join(str(v) for v in s.ravel())
    return str(s)


def _clean(s: str) -> str:
    """Strip MATLAB TeX escapes ($, backslashes) so text renders literally."""
    s = s.replace("$", "").replace("\\", " ")
    return " ".join(s.split())


def _short(s: str, n: int = 40) -> str:
    return s if len(s) <= n else s[: n - 1] + "\u2026"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("fig")
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    render(args.fig, args.save)
