"""Gráficos de barras (1 factor) y de barras agrupadas (2 factores) con matplotlib, sin Qt."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.figure import Figure

from .stats import center_and_error
from .style import PALETTES, PlotStyle
from .twoway import TwoWayData


def _prepare(fig: Figure | None, style: PlotStyle, apply_size: bool) -> Figure:
    if fig is None:
        fig = Figure(figsize=(style.width, style.height), dpi=100)
    fig.clear()
    if apply_size:
        fig.set_size_inches(style.width, style.height)
    return fig


def _colors(palette: str, n: int, distinct: bool = False) -> list[str]:
    """Colores de relleno. distinct=True (leyenda) vuelve distinguibles los tonos de la paleta gris."""
    pal = PALETTES.get(palette, PALETTES["Gris"])
    if len(pal) == 1:
        return [str(g) for g in np.linspace(0.9, 0.4, n)] if distinct and n > 1 else [pal[0]] * n
    return [pal[i % len(pal)] for i in range(n)]


def series_colors(palette: str, n: int) -> list[str]:
    """Colores para líneas/puntos: con la paleta gris, tonos oscuros."""
    pal = PALETTES.get(palette, PALETTES["Gris"])
    if len(pal) == 1:
        return [str(g) for g in np.linspace(0.0, 0.55, n)] if n > 1 else ["black"]
    return [pal[i % len(pal)] for i in range(n)]


def _rotation(names: list[str], style: PlotStyle, width_in: float) -> tuple[int, str]:
    if style.label_rotation in ("0", "45", "90"):
        rot = int(style.label_rotation)
    else:  # auto: estima si las etiquetas caben en horizontal
        est_width = sum(len(n) for n in names) * style.font_size * 0.65
        rot = 0 if est_width <= width_in * 72 * 0.8 else 45
    return rot, ("right" if rot == 45 else "center")


def grouped_layout(td: TwoWayData):
    """Posición X de cada celda (A, B) en barras/cajas agrupadas."""
    la, lb = td.levels_a(), td.levels_b()
    bw = 0.8 / len(lb)
    pos = {(a, b): i + (j - (len(lb) - 1) / 2) * bw for i, a in enumerate(la) for j, b in enumerate(lb)}
    return la, lb, bw, pos


def _empty(fig: Figure) -> Figure:
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()
    return fig


def _finish(ax, style: PlotStyle, xlabel: str, ylabel: str, rot: int, ha: str, ticks, labels) -> None:
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=rot, ha=ha, fontsize=style.font_size)
    ax.tick_params(axis="y", labelsize=style.font_size)
    ax.set_xlabel(xlabel, fontsize=style.font_size + 1)
    ax.set_ylabel(ylabel, fontsize=style.font_size + 1)
    if style.title:
        ax.set_title(style.title, fontsize=style.font_size + 3)
    ax.set_ylim(bottom=style.ymin, top=style.ymax)
    ax.spines[["top", "right"]].set_visible(False)


def _top(center, hi, vals, show_points) -> float:
    if math.isnan(center):
        return math.nan
    t = center + (0.0 if math.isnan(hi) else hi)
    if show_points:
        pts = [v for v in vals if not math.isnan(v)]
        t = max([t] + pts)
    return t


def make_bar_figure(data: dict[str, list[float]], style: PlotStyle, fig: Figure | None = None,
                    apply_size: bool = True, comparisons: list[tuple] | None = None) -> Figure:
    """Barras de 1 factor. apply_size=False respeta el tamaño actual de la figura (lienzo de la UI)."""
    fig = _prepare(fig, style, apply_size)
    if not data:
        return _empty(fig)
    ax = fig.add_subplot(111)
    names = list(data)
    ce = [center_and_error(v, style.error_type) for v in data.values()]
    nz = lambda x: 0.0 if math.isnan(x) else x  # noqa: E731
    centers = [nz(c) for c, _, _ in ce]
    x = np.arange(len(names))
    ax.bar(x, centers, width=0.65, color=_colors(style.palette, len(names)), edgecolor="black", linewidth=1,
           yerr=[[nz(lo) for _, lo, _ in ce], [nz(hi) for _, _, hi in ce]], capsize=5,
           error_kw={"elinewidth": 1.2, "capthick": 1.2}, zorder=2)
    if style.show_points:
        rng = np.random.default_rng(0)
        for i, vals in enumerate(data.values()):
            vals = [v for v in vals if not math.isnan(v)]
            ax.scatter(i + rng.uniform(-0.12, 0.12, len(vals)), vals, s=18, color="black", zorder=3)
    rot, ha = _rotation(names, style, fig.get_figwidth())
    _finish(ax, style, style.xlabel or "Grupo", style.ylabel or "Valor", rot, ha, x, names)
    if comparisons:
        pos = {n: float(i) for i, n in enumerate(names)}
        tops = [(float(i), _top(c, hi, v, style.show_points)) for i, ((c, _, hi), v) in enumerate(zip(ce, data.values()))]
        items = [(pos[a], pos[b], lab) for a, b, lab in comparisons if a in pos and b in pos]
        _draw_brackets(ax, tops, items, style)
    fig.tight_layout()
    return fig


def make_grouped_figure(td: TwoWayData, style: PlotStyle, fig: Figure | None = None,
                        apply_size: bool = True, comparisons: list[tuple] | None = None) -> Figure:
    """Barras agrupadas de 2 factores: eje X = factor A, leyenda/colores = factor B."""
    fig = _prepare(fig, style, apply_size)
    if not td.y:
        return _empty(fig)
    ax = fig.add_subplot(111)
    la, lb = td.levels_a(), td.levels_b()
    cells = td.cells()
    nb = len(lb)
    bw = 0.8 / nb
    colors = _colors(style.palette, nb, distinct=True)
    nz = lambda x: 0.0 if math.isnan(x) else x  # noqa: E731
    rng = np.random.default_rng(0)
    pos, tops, all_centers = {}, [], []
    for j, b in enumerate(lb):
        xs, cs, los, his = [], [], [], []
        for i, a in enumerate(la):
            x = i + (j - (nb - 1) / 2) * bw
            vals = cells.get((a, b), [])
            c, lo, hi = center_and_error(vals, style.error_type)
            xs.append(x); cs.append(nz(c)); los.append(nz(lo)); his.append(nz(hi))
            pos[(a, b)] = x
            all_centers.append(nz(c))
            t = _top(c, hi, vals, style.show_points)
            if not math.isnan(t):
                tops.append((x, t))
            if style.show_points and vals:
                ax.scatter(x + rng.uniform(-bw * 0.25, bw * 0.25, len(vals)), vals, s=16, color="black", zorder=3)
        ax.bar(xs, cs, width=bw * 0.92, color=colors[j], edgecolor="black", linewidth=1, label=str(b),
               yerr=[los, his], capsize=3, error_kw={"elinewidth": 1.1, "capthick": 1.1}, zorder=2)
    rot, ha = _rotation([str(a) for a in la], style, fig.get_figwidth())
    xlabel = td.a_name if style.xlabel in ("", "Grupo") else style.xlabel
    ylabel = td.y_name if style.ylabel in ("", "Valor") else style.ylabel
    _finish(ax, style, xlabel, ylabel, rot, ha, np.arange(len(la)), [str(a) for a in la])
    if comparisons:
        items = [(pos[a], pos[b], lab) for a, b, lab in comparisons if a in pos and b in pos]
        _draw_brackets(ax, tops, items, style)
    ax.legend(title=td.b_name, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              fontsize=style.font_size, title_fontsize=style.font_size)
    fig.tight_layout()
    return fig


def _draw_brackets(ax, bars: list[tuple[float, float]], items: list[tuple[float, float, str]],
                   style: PlotStyle) -> None:
    """Corchetes con asteriscos (o 'ns') sobre las barras; se apilan sin solaparse."""
    if not bars or not items:
        return
    lo = ax.get_ylim()[0]
    max_top = max(t for _, t in bars)
    span = max(max_top - lo, 1e-9)
    step, tick, pad = 0.10 * span, 0.02 * span, 0.04 * span
    ordered = sorted(((min(a, b), max(a, b), lab) for a, b, lab in items), key=lambda t: (t[1] - t[0], t[0]))
    placed: list[tuple[float, float, float]] = []
    top_y = max_top
    for x1, x2, lab in ordered:
        under = [t for x, t in bars if x1 - 1e-9 <= x <= x2 + 1e-9]
        y = (max(under) if under else max_top) + pad
        for px1, px2, py in placed:
            if not (x2 < px1 or x1 > px2):  # se solapan en X
                y = max(y, py + step)
        placed.append((x1, x2, y))
        ax.plot([x1, x1, x2, x2], [y - tick, y, y, y - tick], color="black", lw=1.1, zorder=4,
                solid_capstyle="butt")
        small = lab == "ns"
        ax.text((x1 + x2) / 2, y + (0.005 if small else -0.012) * span, lab, ha="center", va="bottom",
                fontsize=style.font_size - (1 if small else 0) + (0 if small else 2), zorder=4)
        top_y = max(top_y, y + step * 0.9)
    if style.ymax is None:
        ax.set_ylim(bottom=style.ymin, top=top_y + 0.02 * span)
        # el eje solo muestra valores de datos, no el espacio ocupado por los corchetes
        ticks = [t for t in ax.get_yticks() if lo <= t <= max_top + 1e-9]
        if ticks:
            ax.set_yticks(ticks)
            ax.spines["left"].set_bounds(lo, ticks[-1])
