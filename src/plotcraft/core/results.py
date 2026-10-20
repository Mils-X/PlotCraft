"""Estructuras de resultados y formato (HTML) compartidos por todas las pruebas."""
from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

from .posthoc import Comparison


@dataclass
class GroupStats:
    name: str
    n: int
    mean: float
    sd: float
    median: float = math.nan


@dataclass
class AnalysisResult:
    title: str
    alpha: float
    groups: list[GroupStats]
    summary: list[tuple[str, str]] = field(default_factory=list)
    anova: list[tuple] | None = None   # (fuente, SC, gl, CM, F, p, % variación)
    posthoc_name: str | None = None
    comparisons: list[Comparison] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    diff_label: str = "Dif. de medias"
    stat_label: str = "Estadístico"
    show_median: bool = False


def stars(p: float, alpha: float = 0.05) -> str:
    if p is None or math.isnan(p) or p >= alpha:
        return "ns"
    if p < 0.0001:
        return "****"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    return "*"


def significance_labels(result: AnalysisResult, show_ns: bool = False) -> list[tuple]:
    """(clave_a, clave_b, etiqueta): la clave es el nombre del grupo, o (nivel_A, nivel_B) en 2 factores."""
    out = []
    for c in result.comparisons:
        lab = stars(c.p, result.alpha)
        if lab != "ns" or show_ns:
            out.append((c.a if c.a_key is None else c.a_key, c.b if c.b_key is None else c.b_key, lab))
    return out


def fmt_p(p) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "—"
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def _g(x, nd=4):
    return "" if x is None else ("—" if isinstance(x, float) and math.isnan(x) else f"{x:.{nd}g}")


def _table(header, rows):
    th = "".join(f"<th style='text-align:left;padding:3px 10px;border-bottom:1px solid #888'>{h}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td style='padding:3px 10px'>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table cellspacing='0'><tr>{th}</tr>{body}</table>"


def result_to_html(r: AnalysisResult) -> str:
    e = html.escape
    parts = [f"<h3>{e(r.title)}</h3>"]
    if r.summary:
        parts.append(_table(["Resultado", "Valor"], [(e(k), e(v)) for k, v in r.summary]))
    parts.append("<br><h4>Grupos</h4>")
    if r.show_median:
        parts.append(_table(["Grupo", "n", "Mediana", "Media", "DE"],
                            [(e(g.name), g.n, _g(g.median), _g(g.mean), _g(g.sd)) for g in r.groups]))
    else:
        parts.append(_table(["Grupo", "n", "Media", "DE"],
                            [(e(g.name), g.n, _g(g.mean), _g(g.sd)) for g in r.groups]))
    if r.anova:
        parts.append("<br><h4>Tabla ANOVA</h4>")
        parts.append(_table(["Fuente", "SC", "gl", "CM", "F", "p", "% de la variación"],
                            [(e(a), _g(b), c, _g(d), _g(f), e(fmt_p(p)) if p is not None else "",
                              "" if pct is None else f"{pct:.2f}%")
                             for a, b, c, d, f, p, pct in r.anova]))
    if r.comparisons:
        title = f"Comparaciones múltiples — {e(r.posthoc_name)}" if r.posthoc_name else "Comparación"
        parts.append(f"<br><h4>{title}</h4>")
        has_ci = any(c.ci_low is not None for c in r.comparisons)
        header = ["Comparación", r.diff_label] + ([f"IC{round((1 - r.alpha) * 100)}%"] if has_ci else []) \
            + [r.stat_label, "p ajustada", "Signif."]
        rows = []
        for c in r.comparisons:
            row = [f"{e(c.a)} vs {e(c.b)}", _g(c.diff)]
            if has_ci:
                row.append("" if c.ci_low is None else f"{_g(c.ci_low)} a {_g(c.ci_high)}")
            row += [_g(c.stat), e(fmt_p(c.p)), stars(c.p, r.alpha)]
            rows.append(row)
        parts.append(_table(header, rows))
    for n in r.notes:
        parts.append(f"<p><i>{e(n)}</i></p>")
    return "".join(parts)
