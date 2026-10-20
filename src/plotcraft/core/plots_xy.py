"""Dispersión, líneas y puntos, líneas, y burbujas 2D."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.figure import Figure
from scipy import stats

from .plotting import _colors, _empty, _prepare, series_colors
from .stats import center_and_error
from .style import DOSE_RESPONSE, PlotStyle
from .xydata import BubbleData, XYData

MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]
KINDS = ("Dispersión", "Líneas y puntos", "Líneas", DOSE_RESPONSE)


def _style_axes(ax, style: PlotStyle, xlabel: str, ylabel: str) -> None:
    ax.tick_params(labelsize=style.font_size)
    ax.set_xlabel(xlabel, fontsize=style.font_size + 1)
    ax.set_ylabel(ylabel, fontsize=style.font_size + 1)
    if style.title:
        ax.set_title(style.title, fontsize=style.font_size + 3)
    if style.x_log:
        ax.set_xscale("log", nonpositive="mask")
    if style.y_log:
        ax.set_yscale("log", nonpositive="mask")
    ax.set_ylim(bottom=style.ymin, top=style.ymax)
    ax.spines[["top", "right"]].set_visible(False)


def _label(user: str, defaults: tuple, fallback: str) -> str:
    return fallback if user in defaults else user


def trend_line(xs, ys):
    """Recta de mínimos cuadrados: (pendiente, ordenada, R²)."""
    r = stats.linregress(xs, ys)
    return float(r.slope), float(r.intercept), float(r.rvalue ** 2)


def _curve_x(xs) -> np.ndarray:
    """Dosis donde dibujar la curva: el rango de los datos (+5 % en escala log), denso en log y en lineal."""
    pos = [x for x in xs if x > 0]
    if len(pos) < 2 or min(pos) == max(pos):
        return np.array(pos or [1.0])
    lo, hi = min(pos), max(pos)
    ext = (hi / lo) ** 0.05
    lo, hi = lo / ext, hi * ext
    return np.unique(np.concatenate([np.geomspace(lo, hi, 300), np.linspace(lo, hi, 300)]))


def make_dose_response_figure(xy: XYData, style: PlotStyle, fig: Figure | None = None, apply_size: bool = True,
                              fits: dict | None = None, guides: bool = True) -> Figure:
    """Puntos (media ± error por dosis) y curva 4PL ajustada, con el IC50 en la leyenda y guías opcionales."""
    fig = _prepare(fig, style, apply_size)
    series = {n: xy.points(n) for n in xy.series}
    series = {n: p for n, p in series.items() if p}
    if not series:
        return _empty(fig)
    ax = fig.add_subplot(111)
    colors = series_colors(style.palette, len(series))
    fits = fits or {}
    drawn = []
    for k, (name, pts) in enumerate(series.items()):
        c, m = colors[k], MARKERS[k % len(MARKERS)]
        groups: dict[float, list[float]] = {}
        for x, y in pts:
            groups.setdefault(x, []).append(y)
        xs = sorted(groups)
        ce = [center_and_error(groups[x], style.error_type) for x in xs]
        has_err = any(len(groups[x]) > 1 for x in xs)
        ax.errorbar(xs, [c_ for c_, _, _ in ce], yerr=[[lo for _, lo, _ in ce], [hi for _, _, hi in ce]] if has_err else None,
                    color=c, marker=m, markersize=style.marker_size, linestyle="", capsize=3, zorder=3)
        fit = fits.get(name)
        if fit is not None:
            cx = _curve_x(xs)
            ax.plot(cx, fit.curve(cx), color=c, linewidth=style.line_width, zorder=2,
                    label=f"{name} (IC50 = {fit.ic50:.3g})")
            drawn.append((fit, c, cx))
        else:
            ax.plot([], [], color=c, marker=m, linestyle="", label=name)
    only = next(iter(series)) if len(series) == 1 else "Respuesta"
    _style_axes(ax, style, _label(style.xlabel, ("", "Grupo"), xy.x_name),
                _label(style.ylabel, ("", "Valor"), only))
    if guides and not style.y_log:
        y0 = ax.get_ylim()[0]
        for fit, c, cx in drawn:
            ic = fit.ic50
            if math.isfinite(ic) and cx[0] <= ic <= cx[-1]:
                ax.plot([ic, ic], [y0, float(fit.curve(ic))], color=c, linestyle=":", linewidth=1.2, zorder=1)
    ax.legend(frameon=False, fontsize=style.font_size - 1)
    fig.tight_layout()
    return fig


def make_xy_figure(xy: XYData, style: PlotStyle, fig: Figure | None = None, apply_size: bool = True,
                   kind: str = "Dispersión", comparisons=None, fits: dict | None = None,
                   guides: bool = True) -> Figure:
    if kind == DOSE_RESPONSE:
        return make_dose_response_figure(xy, style, fig, apply_size, fits, guides)
    fig = _prepare(fig, style, apply_size)
    series = {n: xy.points(n) for n in xy.series}
    series = {n: p for n, p in series.items() if p}
    if not series:
        return _empty(fig)
    ax = fig.add_subplot(111)
    colors = series_colors(style.palette, len(series))
    lines = kind in ("Líneas y puntos", "Líneas")
    markers = kind in ("Dispersión", "Líneas y puntos")
    for k, (name, pts) in enumerate(series.items()):
        c, m = colors[k], MARKERS[k % len(MARKERS)]
        if lines and style.average_reps:
            groups: dict[float, list[float]] = {}
            for x, y in pts:
                groups.setdefault(x, []).append(y)
            xs = sorted(groups)
            ce = [center_and_error(groups[x], style.error_type) for x in xs]
            has_err = any(len(groups[x]) > 1 for x in xs)
            ax.errorbar(xs, [c_ for c_, _, _ in ce], yerr=[[lo for _, lo, _ in ce], [hi for _, _, hi in ce]] if has_err else None,
                        color=c, marker=m if markers else "", markersize=style.marker_size, linestyle="-",
                        linewidth=style.line_width, capsize=3, label=name)
        elif lines:
            pts = sorted(pts)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, marker=m if markers else "",
                    markersize=style.marker_size, linewidth=style.line_width, label=name)
        else:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=style.marker_size ** 2, marker=m, color=c,
                       edgecolors="black", linewidths=0.5, label=name, zorder=3)
            xs_, ys_ = [p[0] for p in pts], [p[1] for p in pts]
            if style.trendline and len(pts) >= 3 and len(set(xs_)) >= 2:
                slope, icpt, r2 = trend_line(xs_, ys_)
                xx = np.linspace(min(xs_), max(xs_), 100)
                sign = "+" if icpt >= 0 else "−"
                ax.plot(xx, icpt + slope * xx, color=c, linestyle="--", linewidth=1.2,
                        label=f"{name}: y = {slope:.3g}x {sign} {abs(icpt):.3g} (R² = {r2:.3f})")
    only = next(iter(series)) if len(series) == 1 else "Valor"
    _style_axes(ax, style, _label(style.xlabel, ("", "Grupo"), xy.x_name),
                _label(style.ylabel, ("", "Valor"), only))
    if len(series) > 1 or (kind == "Dispersión" and style.trendline):
        ax.legend(frameon=False, fontsize=style.font_size - 1)
    fig.tight_layout()
    return fig


MAX_AREA = 1100.0  # pt² de la burbuja más grande con escala 1


def bubble_areas(sizes, scale: float = 1.0) -> np.ndarray:
    """Área proporcional al tamaño (no el radio), con un mínimo para que las pequeñas se vean."""
    sizes = np.asarray(sizes, dtype=float)
    return np.maximum(sizes / sizes.max() * MAX_AREA * scale, 5.0)


def make_bubble_figure(bd: BubbleData, style: PlotStyle, fig: Figure | None = None,
                       apply_size: bool = True, comparisons=None) -> Figure:
    fig = _prepare(fig, style, apply_size)
    rows = [(x, y, s, g) for x, y, s, g in zip(bd.x, bd.y, bd.size, bd.group or [""] * len(bd.x))
            if not (math.isnan(x) or math.isnan(y) or math.isnan(s)) and s > 0]
    if not rows:
        return _empty(fig)
    ax = fig.add_subplot(111)
    sizes = np.array([r[2] for r in rows])
    areas = bubble_areas(sizes, style.bubble_scale)
    groups = list(dict.fromkeys(r[3] for r in rows))
    has_groups = any(groups) and len(groups) > 0
    colors = _colors(style.palette, len(groups), distinct=True) if len(groups) > 1 else \
        ([_colors(style.palette, 1)[0]] if style.palette != "Gris" else ["#8C8C8C"])
    gcolor = {g: colors[i % len(colors)] for i, g in enumerate(groups)}
    for g in groups:
        sel = [i for i, r in enumerate(rows) if r[3] == g]
        ax.scatter([rows[i][0] for i in sel], [rows[i][1] for i in sel], s=areas[sel], color=gcolor[g], alpha=0.6,
                   edgecolors="black", linewidths=0.8, label=g or " ", zorder=3)
    ax.margins(0.12)
    _style_axes(ax, style, _label(style.xlabel, ("", "Grupo"), bd.x_name),
                _label(style.ylabel, ("", "Valor"), bd.y_name))
    leg1 = None
    if has_groups and len(groups) > 1:
        from matplotlib.lines import Line2D
        handles = [Line2D([], [], marker="o", linestyle="", markersize=9, markerfacecolor=gcolor[g], alpha=0.8,
                          markeredgecolor="black", label=g) for g in groups]
        leg1 = ax.legend(handles=handles, title=bd.group_name, frameon=False, loc="upper left",
                         bbox_to_anchor=(1.01, 1.0), fontsize=style.font_size, title_fontsize=style.font_size)
        ax.add_artist(leg1)
    ref = sorted({float(np.min(sizes)), float(np.median(sizes)), float(np.max(sizes))})
    handles = [ax.scatter([], [], s=float(bubble_areas(np.append(sizes, v), style.bubble_scale)[-1]),
                          color="lightgray", edgecolors="black", linewidths=0.8, label=f"{v:g}") for v in ref]
    ax.legend(handles=handles, title=bd.size_name, frameon=False, loc="lower left" if leg1 else "upper left",
              bbox_to_anchor=(1.01, 0.0) if leg1 else (1.01, 1.0), labelspacing=1.4, borderpad=1.0,
              fontsize=style.font_size, title_fontsize=style.font_size)
    fig.tight_layout()
    return fig
