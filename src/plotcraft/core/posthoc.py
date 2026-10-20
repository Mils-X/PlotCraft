"""Pruebas post hoc de comparaciones múltiples.

Tukey (Tukey-Kramer), Bonferroni, Sidak, Holm-Sidak y Newman-Keuls usan el error cuadrático medio
(MSE) combinado con sus grados de libertad, que pueden venir de un ANOVA de una vía o de dos vías.
Dunnett usa scipy (integración numérica).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

POSTHOC_METHODS = ("Tukey", "Dunnett", "Bonferroni", "Sidak", "Holm-Sidak", "Newman-Keuls")


@dataclass
class Comparison:
    a: str
    b: str
    diff: float            # media(a) - media(b) (o la diferencia que indique el resultado)
    stat: float            # t, q, z, U... según el método
    p: float               # p ajustada
    ci_low: float | None = None
    ci_high: float | None = None
    a_key: object = None   # clave para ubicar la barra en el gráfico (2 factores)
    b_key: object = None


def adjust_p(raw, method: str) -> np.ndarray:
    raw = np.asarray(raw, dtype=float)
    m = len(raw)
    if method == "Bonferroni":
        return np.minimum(1.0, raw * m)
    if method == "Sidak":
        return 1 - (1 - raw) ** m
    if method in ("Holm-Sidak", "Holm"):
        order = np.argsort(raw)
        adj = np.empty(m)
        running = 0.0
        for rank, idx in enumerate(order):
            if method == "Holm-Sidak":
                v = 1 - (1 - raw[idx]) ** (m - rank)
            else:
                v = min(1.0, (m - rank) * raw[idx])
            running = max(running, v)
            adj[idx] = running
        return adj
    raise ValueError(f"Ajuste desconocido: {method}")


def pooled_stats(samples: list[np.ndarray]):
    ns = np.array([len(s) for s in samples], dtype=float)
    means = np.array([s.mean() for s in samples])
    dfe = int(ns.sum() - len(samples))
    if dfe <= 0:
        raise ValueError("No hay suficientes réplicas para el post hoc (se necesitan más datos que grupos).")
    ssw = float(sum(((s - s.mean()) ** 2).sum() for s in samples))
    return ns, means, ssw / dfe, dfe


def _pairs(k: int):
    return list(itertools.combinations(range(k), 2))


def tukey_stats(names, ns, means, mse, dfe, alpha):
    k = len(names)
    qcrit = float(stats.studentized_range.ppf(1 - alpha, k, dfe))
    out = []
    for i, j in _pairs(k):
        diff = float(means[i] - means[j])
        se = math.sqrt(mse / 2 * (1 / ns[i] + 1 / ns[j]))
        if se > 0:
            q = abs(diff) / se
            p = float(stats.studentized_range.sf(q, k, dfe))
        else:
            q, p = math.nan, math.nan
        out.append(Comparison(names[i], names[j], diff, q, p, diff - qcrit * se, diff + qcrit * se))
    return out


def adjusted_stats(method, names, ns, means, mse, dfe, alpha):
    pairs = _pairs(len(names))
    m = len(pairs)
    rows = []
    for i, j in pairs:
        diff = float(means[i] - means[j])
        se = math.sqrt(mse * (1 / ns[i] + 1 / ns[j]))
        t = diff / se if se > 0 else math.nan
        p = float(2 * stats.t.sf(abs(t), dfe)) if se > 0 else math.nan
        rows.append((i, j, diff, se, t, p))
    adj = adjust_p([r[5] for r in rows], method)
    if method == "Bonferroni":
        a_ci = alpha / m
    elif method == "Sidak":
        a_ci = 1 - (1 - alpha) ** (1 / m)
    else:
        a_ci = None  # Holm-Sidak: sin IC
    crit = float(stats.t.ppf(1 - a_ci / 2, dfe)) if a_ci is not None else None
    out = []
    for (i, j, diff, se, t, _), p in zip(rows, adj):
        lo = hi = None
        if crit is not None:
            lo, hi = diff - crit * se, diff + crit * se
        out.append(Comparison(names[i], names[j], diff, float(t), float(p), lo, hi))
    return out


def snk_stats(names, ns, means, mse, dfe, alpha):
    """Newman-Keuls (SNK): rangos escalonados. Una comparación solo es significativa si todos los
    rangos que la contienen también lo son (p = máx(p propia, p de los rangos mayores))."""
    k = len(names)
    order = list(np.argsort(means))
    padj: dict[tuple[int, int], float] = {}
    qs: dict[tuple[int, int], float] = {}
    for r in range(k, 1, -1):
        for lo in range(0, k - r + 1):
            hi = lo + r - 1
            i, j = order[lo], order[hi]
            se = math.sqrt(mse / 2 * (1 / ns[i] + 1 / ns[j]))
            q = abs(means[i] - means[j]) / se if se > 0 else math.nan
            p = float(stats.studentized_range.sf(q, r, dfe)) if se > 0 else math.nan
            enclosing = []
            if lo > 0:
                enclosing.append(padj[(lo - 1, hi)])
            if hi < k - 1:
                enclosing.append(padj[(lo, hi + 1)])
            padj[(lo, hi)] = max([p] + enclosing)
            qs[(lo, hi)] = q
    pos = {idx: p for p, idx in enumerate(order)}
    out = []
    for i, j in _pairs(k):
        lo, hi = sorted((pos[i], pos[j]))
        out.append(Comparison(names[i], names[j], float(means[i] - means[j]), qs[(lo, hi)], padj[(lo, hi)]))
    return out


def run_posthoc_stats(method, names, ns, means, mse, dfe, alpha=0.05):
    """Post hoc a partir de n, medias y MSE/gl (de un ANOVA de 1 o 2 vías)."""
    if method == "Tukey":
        return tukey_stats(names, ns, means, mse, dfe, alpha)
    if method in ("Bonferroni", "Sidak", "Holm-Sidak"):
        return adjusted_stats(method, names, ns, means, mse, dfe, alpha)
    if method == "Newman-Keuls":
        return snk_stats(names, ns, means, mse, dfe, alpha)
    raise ValueError(f"Post hoc no disponible aquí: {method}")


def dunnett(names, samples, alpha, control):
    if control not in names:
        raise ValueError("Elige un grupo control válido para Dunnett.")
    c = names.index(control)
    others = [i for i in range(len(names)) if i != c]
    # scipy integra numéricamente con muestreo aleatorio: semilla fija para resultados reproducibles
    args = [samples[i] for i in others]
    try:
        res = stats.dunnett(*args, control=samples[c], rng=np.random.default_rng(12345))
    except TypeError:  # scipy < 1.15
        res = stats.dunnett(*args, control=samples[c], random_state=np.random.default_rng(12345))
    ci = res.confidence_interval(1 - alpha)
    out = []
    for k, i in enumerate(others):
        diff = float(samples[i].mean() - samples[c].mean())
        out.append(Comparison(names[i], names[c], diff, float(res.statistic[k]),
                              float(res.pvalue[k]), float(ci.low[k]), float(ci.high[k])))
    return out


def run_posthoc(method, names, samples, alpha=0.05, control=None):
    samples = [np.asarray(s, dtype=float) for s in samples]
    if method == "Dunnett":
        return dunnett(names, samples, alpha, control)
    ns, means, mse, dfe = pooled_stats(samples)
    return run_posthoc_stats(method, names, ns, means, mse, dfe, alpha)
