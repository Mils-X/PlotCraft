"""Cajas y bigotes (1 y 2 factores) e histogramas."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from .plotting import (_colors, _draw_brackets, _empty, _finish, _prepare, _rotation, grouped_layout)
from .style import WHISKERS, PlotStyle
from .twoway import TwoWayData


def _clean(vals) -> np.ndarray:
    return np.array([v for v in vals if v is not None and not math.isnan(v)], dtype=float)


def _draw_boxes(ax, arrays, positions, width, colors, style: PlotStyle):
    minmax = style.whisker == WHISKERS[1]
    bp = ax.boxplot(
        arrays, positions=positions, widths=width, patch_artist=True, manage_ticks=False,
        whis=(0, 100) if minmax else 1.5, showfliers=(not minmax and not style.show_points),
        flierprops={"marker": "o", "markersize": 4, "markerfacecolor": "none"},
        medianprops={"color": "black", "linewidth": 1.6}, whiskerprops={"linewidth": 1.1},
        capprops={"linewidth": 1.1}, boxprops={"linewidth": 1.1})
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_edgecolor("black")
    if style.show_points:
        rng = np.random.default_rng(0)
        for x, arr in zip(positions, arrays):
            ax.scatter(x + rng.uniform(-width * 0.25, width * 0.25, len(arr)), arr, s=16, color="black", zorder=4)
    return bp


def make_box_figure(data: dict[str, list[float]], style: PlotStyle, fig: Figure | None = None,
                    apply_size: bool = True, comparisons: list[tuple] | None = None) -> Figure:
    fig = _prepare(fig, style, apply_size)
    arrays = {n: _clean(v) for n, v in data.items()}
    arrays = {n: a for n, a in arrays.items() if a.size}
    if not arrays:
        return _empty(fig)
    ax = fig.add_subplot(111)
    names = list(arrays)
    x = np.arange(len(names))
    _draw_boxes(ax, list(arrays.values()), list(x), 0.6, _colors(style.palette, len(names)), style)
    rot, ha = _rotation(names, style, fig.get_figwidth())
    _finish(ax, style, style.xlabel or "Grupo", style.ylabel or "Valor", rot, ha, x, names)
    if comparisons:
        pos = {n: float(i) for i, n in enumerate(names)}
        tops = [(float(i), float(a.max())) for i, a in enumerate(arrays.values())]
        items = [(pos[a], pos[b], lab) for a, b, lab in comparisons if a in pos and b in pos]
        _draw_brackets(ax, tops, items, style)
    fig.tight_layout()
    return fig


def make_grouped_box_figure(td: TwoWayData, style: PlotStyle, fig: Figure | None = None,
                            apply_size: bool = True, comparisons: list[tuple] | None = None) -> Figure:
    fig = _prepare(fig, style, apply_size)
    if not td.y:
        return _empty(fig)
    ax = fig.add_subplot(111)
    la, lb, bw, pos = grouped_layout(td)
    cells = td.cells()
    colors = _colors(style.palette, len(lb), distinct=True)
    tops = []
    for j, b in enumerate(lb):
        keys = [(a, b) for a in la if (a, b) in cells]
        arrays = [_clean(cells[k]) for k in keys]
        _draw_boxes(ax, arrays, [pos[k] for k in keys], bw * 0.85, [colors[j]] * len(keys), style)
        tops += [(pos[k], float(a.max())) for k, a in zip(keys, arrays) if a.size]
    rot, ha = _rotation([str(a) for a in la], style, fig.get_figwidth())
    xlabel = td.a_name if style.xlabel in ("", "Grupo") else style.xlabel
    ylabel = td.y_name if style.ylabel in ("", "Valor") else style.ylabel
    _finish(ax, style, xlabel, ylabel, rot, ha, np.arange(len(la)), [str(a) for a in la])
    if comparisons:
        items = [(pos[a], pos[b], lab) for a, b, lab in comparisons if a in pos and b in pos]
        _draw_brackets(ax, tops, items, style)
    handles = [Patch(facecolor=c, edgecolor="black", label=str(b)) for c, b in zip(colors, lb)]
    ax.legend(handles=handles, title=td.b_name, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              fontsize=style.font_size, title_fontsize=style.font_size)
    fig.tight_layout()
    return fig


def make_hist_figure(data: dict[str, list[float]], style: PlotStyle, fig: Figure | None = None,
                     apply_size: bool = True, comparisons: list[tuple] | None = None) -> Figure:
    """Histogramas superpuestos con los mismos intervalos (bins) para todos los grupos."""
    fig = _prepare(fig, style, apply_size)
    arrays = {n: _clean(v) for n, v in data.items()}
    arrays = {n: a for n, a in arrays.items() if a.size}
    if not arrays:
        return _empty(fig)
    ax = fig.add_subplot(111)
    allv = np.concatenate(list(arrays.values()))
    edges = np.histogram_bin_edges(allv, bins=style.bins if style.bins > 0 else "auto")
    n = len(arrays)
    colors = _colors(style.palette, n, distinct=True)
    for (name, arr), c in zip(arrays.items(), colors):
        ax.hist(arr, bins=edges, density=style.density, color=c, edgecolor="black", linewidth=0.9,
                alpha=0.6 if n > 1 else 1.0, label=name)
    ax.tick_params(labelsize=style.font_size)
    ax.set_xlabel("Valor" if style.xlabel in ("", "Grupo") else style.xlabel, fontsize=style.font_size + 1)
    default_y = "Densidad" if style.density else "Frecuencia"
    ax.set_ylabel(default_y if style.ylabel in ("", "Valor") else style.ylabel, fontsize=style.font_size + 1)
    if style.title:
        ax.set_title(style.title, fontsize=style.font_size + 3)
    ax.set_ylim(bottom=style.ymin, top=style.ymax)
    ax.spines[["top", "right"]].set_visible(False)
    if n > 1:
        ax.legend(frameon=False, fontsize=style.font_size)
    fig.tight_layout()
    return fig
