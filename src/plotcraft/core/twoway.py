"""ANOVA de dos vías (SC tipo III, codificación de efectos) con efectos simples y post hoc."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from .posthoc import Comparison, run_posthoc_stats
from .results import AnalysisResult, GroupStats, fmt_p

COMPARE_MODES = ("Leyenda dentro de cada X", "X dentro de cada leyenda", "Ninguna")
TWOWAY_POSTHOC = ("Tukey", "Bonferroni", "Sidak", "Holm-Sidak", "Ninguno")


@dataclass
class TwoWayData:
    """Formato largo: una fila por observación. A = factor del eje X, B = factor de la leyenda."""
    a_name: str = "Factor A"
    b_name: str = "Factor B"
    y_name: str = "Valor"
    a: list[str] = field(default_factory=list)
    b: list[str] = field(default_factory=list)
    y: list[float] = field(default_factory=list)

    def levels_a(self) -> list[str]:
        return list(dict.fromkeys(self.a))

    def levels_b(self) -> list[str]:
        return list(dict.fromkeys(self.b))

    def cells(self) -> dict[tuple[str, str], list[float]]:
        out: dict[tuple[str, str], list[float]] = {}
        for a, b, y in zip(self.a, self.b, self.y):
            out.setdefault((a, b), []).append(y)
        return out

    def swapped(self) -> "TwoWayData":
        return TwoWayData(self.b_name, self.a_name, self.y_name, list(self.b), list(self.a), list(self.y))

    def to_dict(self) -> dict:
        return {"a_name": self.a_name, "b_name": self.b_name, "y_name": self.y_name,
                "a": list(self.a), "b": list(self.b), "y": list(self.y)}

    @classmethod
    def from_dict(cls, d: dict) -> "TwoWayData":
        return cls(d.get("a_name", "Factor A"), d.get("b_name", "Factor B"), d.get("y_name", "Valor"),
                   [str(x) for x in d.get("a", [])], [str(x) for x in d.get("b", [])],
                   [float(x) for x in d.get("y", [])])


def _effect_cols(codes: np.ndarray, levels: int) -> np.ndarray:
    """Codificación de efectos (suma cero): el último nivel vale -1."""
    X = np.zeros((len(codes), levels - 1))
    for j in range(levels - 1):
        X[codes == j, j] = 1.0
        X[codes == levels - 1, j] = -1.0
    return X


def _rss(y: np.ndarray, blocks: list[np.ndarray]) -> tuple[float, int]:
    X = np.column_stack([np.ones(len(y))] + blocks)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return float(resid @ resid), int(np.linalg.matrix_rank(X))


def anova_two_way(td: TwoWayData):
    """Devuelve filas [(término, SC, gl, CM, F, p)], MSE y gl del residual."""
    la, lb = td.levels_a(), td.levels_b()
    y = np.asarray(td.y, dtype=float)
    ca = np.array([la.index(v) for v in td.a])
    cb = np.array([lb.index(v) for v in td.b])
    XA, XB = _effect_cols(ca, len(la)), _effect_cols(cb, len(lb))
    XAB = np.column_stack([XA[:, i] * XB[:, j] for i in range(XA.shape[1]) for j in range(XB.shape[1])])
    blocks = {"A": XA, "B": XB, "AB": XAB}
    rss_full, rank = _rss(y, [XA, XB, XAB])
    dfe = len(y) - rank
    mse = rss_full / dfe
    rows = []
    for key in ("A", "B", "AB"):
        rest = [v for k, v in blocks.items() if k != key]
        rss_red, _ = _rss(y, rest)
        ss, df = rss_red - rss_full, blocks[key].shape[1]
        ms = ss / df
        F = ms / mse if mse > 0 else math.inf
        p = float(stats.f.sf(F, df, dfe)) if mse > 0 else 0.0
        rows.append((key, ss, df, ms, F, p))
    return rows, mse, dfe, rss_full


def run_twoway(td: TwoWayData, alpha: float, posthoc: str, compare: str) -> AnalysisResult:
    if not td.y:
        raise ValueError("No hay datos. Pega tres columnas: Factor A, Factor B y Valor.")
    la, lb = td.levels_a(), td.levels_b()
    if len(la) < 2 or len(lb) < 2:
        raise ValueError("Cada factor necesita al menos 2 niveles distintos.")
    cells = td.cells()
    for a in la:
        for b in lb:
            if (a, b) not in cells:
                raise ValueError(f"Falta la combinación «{a} · {b}»: el diseño debe tener datos en todas las celdas.")
    n = len(td.y)
    if n - len(la) * len(lb) <= 0:
        raise ValueError("Se necesitan réplicas: al menos una celda debe tener 2 o más datos para estimar el error.")

    rows, mse, dfe, rss = anova_two_way(td)
    y = np.asarray(td.y, dtype=float)
    sst = float(((y - y.mean()) ** 2).sum())
    names = {"A": td.a_name, "B": td.b_name, "AB": f"{td.a_name} × {td.b_name}"}
    pct = lambda ss: ss / sst * 100 if sst > 0 else 0.0  # noqa: E731
    res = AnalysisResult("ANOVA de dos vías", alpha, [])
    res.anova = [(names[k], ss, df, ms, F, p, pct(ss)) for k, ss, df, ms, F, p in rows]
    res.anova += [("Residual", rss, dfe, mse, None, None, pct(rss)), ("Total", sst, n - 1, None, None, None, 100.0)]
    p_a, p_b, p_ab = rows[0][5], rows[1][5], rows[2][5]
    res.summary = [("Diseño", f"{len(la)} × {len(lb)} (n = {n})"),
                   (td.a_name, f"F = {rows[0][4]:.4g}, p = {fmt_p(p_a)}"),
                   (td.b_name, f"F = {rows[1][4]:.4g}, p = {fmt_p(p_b)}"),
                   ("Interacción", f"F = {rows[2][4]:.4g}, p = {fmt_p(p_ab)}")]
    for a in la:
        for b in lb:
            v = np.asarray(cells[(a, b)], dtype=float)
            res.groups.append(GroupStats(f"{a} · {b}", len(v), float(v.mean()),
                                         float(v.std(ddof=1)) if len(v) > 1 else math.nan))
    sizes = {len(v) for v in cells.values()}
    if len(sizes) > 1:
        res.notes.append("Diseño desbalanceado: se usan sumas de cuadrados tipo III.")
    if p_ab < alpha:
        res.notes.append("La interacción es significativa: interpreta los efectos principales con cautela "
                         "y apóyate en las comparaciones dentro de cada nivel.")
    if all(len(v) >= 2 for v in cells.values()):
        lev = stats.levene(*[np.asarray(v, float) for v in cells.values()], center="median")
        res.notes.append(f"Homogeneidad de varianzas entre celdas (Brown-Forsythe): p = {fmt_p(float(lev.pvalue))}.")

    if posthoc not in TWOWAY_POSTHOC:
        posthoc = TWOWAY_POSTHOC[0]
    if compare != "Ninguna" and posthoc != "Ninguno":
        res.posthoc_name = f"{posthoc} — {compare}"
        if compare == COMPARE_MODES[0]:      # barras de la leyenda dentro de cada grupo X
            families = [[(a, b) for b in lb] for a in la]
        else:                                # grupos X dentro de cada barra de la leyenda
            families = [[(a, b) for a in la] for b in lb]
        for fam in families:
            labels = [f"{a} · {b}" for a, b in fam]
            ns = np.array([len(cells[k]) for k in fam], dtype=float)
            means = np.array([np.mean(cells[k]) for k in fam])
            comps = run_posthoc_stats(posthoc, labels, ns, means, mse, dfe, alpha)
            idx = {lab: k for lab, k in zip(labels, fam)}
            for c in comps:
                c.a_key, c.b_key = idx[c.a], idx[c.b]
            res.comparisons += comps
        res.notes.append("Cada familia de comparaciones (cada grupo del eje X o de la leyenda) se corrige por separado, "
                         "con el error residual del ANOVA.")
    return res
