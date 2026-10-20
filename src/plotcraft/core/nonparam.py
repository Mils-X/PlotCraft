"""Pruebas no paramétricas: Mann-Whitney, Wilcoxon, Kruskal-Wallis y Friedman (con post hoc de Dunn)."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .posthoc import Comparison, _pairs, adjust_p
from .results import AnalysisResult, fmt_p

NONPARAM_TESTS = ("Mann-Whitney", "Wilcoxon (apareada)", "Kruskal-Wallis", "Friedman")
DUNN_CHOICES = ("Dunn-Bonferroni", "Dunn-Holm", "Dunn-Sidak", "Ninguno")


def mann_whitney(names, samples, alpha) -> AnalysisResult:
    a, b = samples
    if min(len(a), len(b)) < 2:
        raise ValueError("Cada grupo necesita al menos 2 réplicas para Mann-Whitney.")
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    comp = Comparison(names[0], names[1], float(np.median(a) - np.median(b)), float(res.statistic), float(res.pvalue))
    r = AnalysisResult("Mann-Whitney (dos colas)", alpha, [], comparisons=[comp],
                       diff_label="Dif. de medianas", stat_label="U", show_median=True)
    r.summary = [("U", f"{res.statistic:.4g}"), ("p", fmt_p(float(res.pvalue)))]
    r.notes.append("Prueba de suma de rangos: compara las distribuciones. La diferencia de medianas es solo descriptiva.")
    return r


def wilcoxon(names, samples, alpha) -> AnalysisResult:
    a, b = samples
    if len(a) != len(b):
        raise ValueError("Wilcoxon (apareada) necesita el mismo número de réplicas en ambos grupos.")
    d = a - b
    try:
        res = stats.wilcoxon(a, b)
    except ValueError as e:
        raise ValueError(f"Wilcoxon: {e}") from e
    comp = Comparison(names[0], names[1], float(np.median(d)), float(res.statistic), float(res.pvalue))
    r = AnalysisResult("Wilcoxon de rangos con signo (apareada, dos colas)", alpha, [], comparisons=[comp],
                       diff_label="Mediana de las diferencias", stat_label="W", show_median=True)
    r.summary = [("W", f"{res.statistic:.4g}"), ("n de pares", str(len(a))), ("p", fmt_p(float(res.pvalue)))]
    if np.any(d == 0):
        r.notes.append("Las diferencias iguales a cero se descartan.")
    return r


def _dunn_from_z(names, mean_ranks, se_fn, method) -> list[Comparison]:
    pairs = _pairs(len(names))
    zs, raw = [], []
    for i, j in pairs:
        se = se_fn(i, j)
        z = (mean_ranks[i] - mean_ranks[j]) / se if se > 0 else math.nan
        zs.append(z)
        raw.append(float(2 * stats.norm.sf(abs(z))) if se > 0 else math.nan)
    adj = adjust_p(raw, method)
    return [Comparison(names[i], names[j], float(mean_ranks[i] - mean_ranks[j]), float(z), float(p))
            for (i, j), z, p in zip(pairs, zs, adj)]


def dunn(names, samples, method) -> list[Comparison]:
    """Dunn tras Kruskal-Wallis, con corrección por empates. method: Bonferroni, Holm o Sidak."""
    allv = np.concatenate(samples)
    N = len(allv)
    ranks = stats.rankdata(allv)
    edges = np.cumsum([0] + [len(s) for s in samples])
    ns = np.array([len(s) for s in samples], dtype=float)
    mean_ranks = np.array([ranks[edges[i]:edges[i + 1]].mean() for i in range(len(samples))])
    _, counts = np.unique(allv, return_counts=True)
    ties = float((counts ** 3 - counts).sum())
    sigma2 = N * (N + 1) / 12 - ties / (12 * (N - 1))
    return _dunn_from_z(names, mean_ranks, lambda i, j: math.sqrt(sigma2 * (1 / ns[i] + 1 / ns[j])), method)


def kruskal(names, samples, alpha, posthoc) -> AnalysisResult:
    k = len(samples)
    try:
        res = stats.kruskal(*samples)
    except ValueError as e:
        raise ValueError(f"Kruskal-Wallis: {e}") from e
    r = AnalysisResult("Kruskal-Wallis", alpha, [], diff_label="Dif. de rangos promedio",
                       stat_label="z", show_median=True)
    r.summary = [("H (con corrección por empates)", f"{res.statistic:.4g}"), ("gl", str(k - 1)),
                 ("p", fmt_p(float(res.pvalue)))]
    if k == 2:
        r.notes.append("Con 2 grupos conviene Mann-Whitney; el resultado es equivalente.")
    elif posthoc != "Ninguno":
        method = posthoc.replace("Dunn-", "")
        r.posthoc_name = f"Dunn ({method})"
        r.comparisons = dunn(names, samples, method)
        if res.pvalue >= alpha:
            r.notes.append("La prueba global no es significativa; interpreta el post hoc con cautela.")
    return r


def friedman(names, samples, alpha, posthoc) -> AnalysisResult:
    k = len(samples)
    n = len(samples[0])
    if k < 3:
        raise ValueError("Friedman necesita al menos 3 grupos (con 2, usa Wilcoxon apareada).")
    if any(len(s) != n for s in samples):
        raise ValueError("Friedman necesita el mismo número de réplicas en todos los grupos "
                         "(cada fila es un sujeto o bloque).")
    if n < 2:
        raise ValueError("Friedman necesita al menos 2 filas (sujetos).")
    res = stats.friedmanchisquare(*samples)
    r = AnalysisResult("Friedman (medidas repetidas)", alpha, [], diff_label="Dif. de suma de rangos",
                       stat_label="z", show_median=True)
    r.summary = [("χ² de Friedman", f"{res.statistic:.4g}"), ("gl", str(k - 1)), ("n de sujetos", str(n)),
                 ("p", fmt_p(float(res.pvalue)))]
    r.notes.append("Cada fila se trata como un sujeto o bloque (los grupos están apareados por fila).")
    if posthoc != "Ninguno":
        method = posthoc.replace("Dunn-", "")
        r.posthoc_name = f"Dunn ({method})"
        M = np.column_stack(samples)
        rank_sums = np.apply_along_axis(stats.rankdata, 1, M).sum(axis=0)
        se = math.sqrt(n * k * (k + 1) / 6)
        r.comparisons = _dunn_from_z(names, rank_sums, lambda i, j: se, method)
        r.notes.append("Dunn para Friedman sin corrección por empates.")
    return r
