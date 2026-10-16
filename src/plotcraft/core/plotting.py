"""Gráficos de barras con matplotlib (sin dependencia de Qt)."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.figure import Figure

from .stats import summarize
from .style import PALETTES, PlotStyle


def _rotation(names: list[str], style: PlotStyle) -> tuple[int, str]:
    if style.label_rotation in ("0", "45", "90"):
        rot = int(style.label_rotation)
    else:  # auto: estima si las etiquetas caben en horizontal
        est_width = sum(len(n) for n in names) * style.font_size * 0.65
        avail = style.width * 72 * 0.8
        rot = 0 if est_width <= avail else 45
    return rot, ("center" if rot == 0 else "right" if rot == 45 else "center")


def make_bar_figure(
    data: dict[str, list[float]], style: PlotStyle, fig: Figure | None = None
) -> Figure:
    if fig is None:
        fig = Figure(figsize=(style.width, style.height), dpi=100)
    fig.clear()
    fig.set_size_inches(style.width, style.height)
    ax = fig.add_subplot(111)

    if not data:
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    names = list(data)
    sums = [summarize(v, style.error_type) for v in data.values()]
    means = [s.mean if not math.isnan(s.mean) else 0.0 for s in sums]
    errs = [s.error if not math.isnan(s.error) else 0.0 for s in sums]
    palette = PALETTES.get(style.palette, PALETTES["Gris"])
    colors = [palette[i % len(palette)] for i in range(len(names))]
    x = np.arange(len(names))

    ax.bar(x, means, width=0.65, color=colors, edgecolor="black", linewidth=1,
           yerr=errs, capsize=5, error_kw={"elinewidth": 1.2, "capthick": 1.2}, zorder=2)

    if style.show_points:
        rng = np.random.default_rng(0)
        for i, vals in enumerate(data.values()):
            vals = [v for v in vals if not math.isnan(v)]
            jitter = rng.uniform(-0.12, 0.12, len(vals))
            ax.scatter(i + jitter, vals, s=18, color="black", zorder=3)

    rot, ha = _rotation(names, style)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=rot, ha=ha, fontsize=style.font_size)
    ax.tick_params(axis="y", labelsize=style.font_size)
    ax.set_xlabel(style.xlabel, fontsize=style.font_size + 1)
    ax.set_ylabel(style.ylabel, fontsize=style.font_size + 1)
    if style.title:
        ax.set_title(style.title, fontsize=style.font_size + 3)
    ax.set_ylim(bottom=style.ymin, top=style.ymax)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig
