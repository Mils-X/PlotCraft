"""Despachador de análisis: t de Student/Welch/apareada, ANOVA de 1 vía, pruebas no paramétricas y ANOVA de 2 vías."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields

import numpy as np
from scipy import stats

from . import nonparam
from .nonparam import DUNN_CHOICES, NONPARAM_TESTS
from .posthoc import POSTHOC_METHODS, Comparison, run_posthoc
from .results import (AnalysisResult, GroupStats, fmt_p, result_to_html,  # noqa: F401 (reexportados)
                      significance_labels, stars)
from .twoway import COMPARE_MODES, TWOWAY_POSTHOC, TwoWayData, run_twoway

TESTS = ("Automático", "t de Student", "t de Welch", "t apareada", "ANOVA de una vía") + NONPARAM_TESTS
TESTS_TWO = ("ANOVA de dos vías",)
POSTHOC_CHOICES = POSTHOC_METHODS + ("Ninguno",)


def posthoc_choices(test: str) -> tuple[str, ...]:
    if test in ("Automático", "ANOVA de una vía"):
        return POSTHOC_CHOICES
    if test in ("Kruskal-Wallis", "Friedman"):
        return DUNN_CHOICES
    if test == "ANOVA de dos vías":
        return TWOWAY_POSTHOC
    return ()


@dataclass
class AnalysisConfig:
    test: str = "Automático"
    posthoc: str = "Tukey"
    control: str | None = None
    alpha: float = 0.05
    show_stars: bool = True
    show_ns: bool = False
    active: bool = False
    twoway_compare: str = COMPARE_MODES[0]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


def _clean(data: dict[str, list[float]]):
    names, samples = [], []
    for k, v in data.items():
        arr = np.array([x for x in v if x is not None and not math.isnan(x)], dtype=float)
        if arr.size:
            names.append(k)
            samples.append(arr)
    if len(names) < 2:
        raise ValueError("Se necesitan al menos 2 grupos con datos para analizar.")
    return names, samples


def _t_two_groups(kind, names, samples, alpha) -> AnalysisResult:
    a, b = samples
    if min(len(a), len(b)) < 2:
        raise ValueError("Cada grupo necesita al menos 2 réplicas para la prueba t.")
    n1, n2 = len(a), len(b)
    m1, m2 = a.mean(), b.mean()
    v1, v2 = a.var(ddof=1), b.var(ddof=1)
    if kind == "t apareada":
        if n1 != n2:
            raise ValueError("La prueba t apareada necesita el mismo número de réplicas en ambos grupos.")
        d = a - b
        diff, se, df = d.mean(), d.std(ddof=1) / math.sqrt(n1), n1 - 1
    elif kind == "t de Welch":
        se = math.sqrt(v1 / n1 + v2 / n2)
        diff = m1 - m2
        df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se > 0 else n1 + n2 - 2
    else:  # Student
        df = n1 + n2 - 2
        sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / df
        se = math.sqrt(sp2 * (1 / n1 + 1 / n2))
        diff = m1 - m2
    t = diff / se if se > 0 else math.nan
    p = float(2 * stats.t.sf(abs(t), df)) if se > 0 else math.nan
    crit = float(stats.t.ppf(1 - alpha / 2, df))
    comp = Comparison(names[0], names[1], float(diff), float(t), p, float(diff - crit * se), float(diff + crit * se))
    res = AnalysisResult(f"{kind} (dos colas)", alpha, [], comparisons=[comp])
    res.summary = [("t", f"{t:.4g}"), ("gl", f"{df:.4g}"), ("p", fmt_p(p)),
                   (f"IC{round((1 - alpha) * 100)}% de la diferencia", f"{comp.ci_low:.4g} a {comp.ci_high:.4g}")]
    if kind == "t de Student":
        f = max(v1, v2) / min(v1, v2) if min(v1, v2) > 0 else math.inf
        res.notes.append(f"Razón de varianzas (mayor/menor) = {f:.3g}. Si es muy grande, usa la t de Welch.")
    return res


def _normality_note(names, samples, alpha) -> str | None:
    bad = []
    for n, s in zip(names, samples):
        if len(s) >= 3 and np.ptp(s) > 0:
            try:
                if stats.shapiro(s).pvalue < alpha:
                    bad.append(n)
            except Exception:  # noqa: BLE001
                pass
    if bad:
        return ("Normalidad (Shapiro-Wilk): p < α en " + ", ".join(bad) +
                ". Considera una prueba no paramétrica (Kruskal-Wallis). Con pocas réplicas esta prueba tiene poca potencia.")
    return None


def _anova(names, samples, alpha, posthoc, control) -> AnalysisResult:
    k = len(samples)
    ns = np.array([len(s) for s in samples])
    N = int(ns.sum())
    dfe = N - k
    if dfe <= 0:
        raise ValueError("No hay suficientes réplicas: el ANOVA necesita más datos que grupos.")
    grand = np.concatenate(samples).mean()
    ssb = float(sum(len(s) * (s.mean() - grand) ** 2 for s in samples))
    ssw = float(sum(((s - s.mean()) ** 2).sum() for s in samples))
    sst = ssb + ssw
    msb, msw = ssb / (k - 1), ssw / dfe
    F = msb / msw if msw > 0 else math.inf
    p = float(stats.f.sf(F, k - 1, dfe)) if msw > 0 else 0.0
    res = AnalysisResult("ANOVA de una vía", alpha, [])
    pct = lambda ss: ss / sst * 100 if sst > 0 else 0.0  # noqa: E731
    res.anova = [("Entre grupos", ssb, k - 1, msb, F, p, pct(ssb)),
                 ("Residual (dentro)", ssw, dfe, msw, None, None, pct(ssw)),
                 ("Total", sst, N - 1, None, None, None, 100.0)]
    res.summary = [("F", f"{F:.4g}"), ("gl", f"({k - 1}, {dfe})"), ("p", fmt_p(p)),
                   ("R²", f"{ssb / sst:.4f}" if sst > 0 else "—")]
    if all(len(s) >= 2 for s in samples):
        lev = stats.levene(*samples, center="median")
        res.notes.append(f"Homogeneidad de varianzas (Brown-Forsythe): p = {fmt_p(float(lev.pvalue))}. "
                         "Si es significativa, interpreta el ANOVA con cautela.")
    note = _normality_note(names, samples, alpha)
    if note:
        res.notes.append(note)
    if k == 2:
        res.notes.append("Con 2 grupos el post hoc no aplica; es equivalente a una t de Student.")
    elif posthoc != "Ninguno":
        res.posthoc_name = posthoc + (f" (control: {control})" if posthoc == "Dunnett" else "")
        res.comparisons = run_posthoc(posthoc, names, samples, alpha, control)
        if posthoc == "Dunnett":
            res.notes.append("Las p de Dunnett se calculan por integración numérica (precisión ≈ 0.001); "
                             "valores muy pequeños son aproximados.")
        if p >= alpha:
            res.notes.append("El ANOVA global no es significativo; interpreta el post hoc con cautela.")
    return res


def analyze(data: dict[str, list[float]], cfg: AnalysisConfig) -> AnalysisResult:
    """Análisis de una variable con grupos en columnas."""
    names, samples = _clean(data)
    k = len(names)
    test = cfg.test
    if test == "Automático":
        test = "t de Welch" if k == 2 else "ANOVA de una vía"
    choices = posthoc_choices(test)
    posthoc = cfg.posthoc if cfg.posthoc in choices else (choices[0] if choices else "Ninguno")

    two_only = ("t de Student", "t de Welch", "t apareada", "Mann-Whitney", "Wilcoxon (apareada)")
    if test in two_only:
        if k != 2:
            alt = "ANOVA de una vía o Kruskal-Wallis"
            raise ValueError(f"La prueba «{test}» necesita exactamente 2 grupos (hay {k}). Usa {alt}.")
        if test == "Mann-Whitney":
            res = nonparam.mann_whitney(names, samples, cfg.alpha)
        elif test == "Wilcoxon (apareada)":
            res = nonparam.wilcoxon(names, samples, cfg.alpha)
        else:
            res = _t_two_groups(test, names, samples, cfg.alpha)
    elif test == "Kruskal-Wallis":
        res = nonparam.kruskal(names, samples, cfg.alpha, posthoc)
    elif test == "Friedman":
        res = nonparam.friedman(names, samples, cfg.alpha, posthoc)
    elif test == "ANOVA de una vía":
        control = cfg.control if cfg.control in names else names[0]
        res = _anova(names, samples, cfg.alpha, posthoc, control)
    else:
        raise ValueError(f"Prueba desconocida: {test}")
    res.groups = [GroupStats(n, len(s), float(s.mean()), float(s.std(ddof=1)) if len(s) > 1 else math.nan,
                             float(np.median(s))) for n, s in zip(names, samples)]
    return res


def analyze_twoway(td: TwoWayData, cfg: AnalysisConfig) -> AnalysisResult:
    """ANOVA de dos vías sobre datos en formato largo."""
    return run_twoway(td, cfg.alpha, cfg.posthoc, cfg.twoway_compare)
