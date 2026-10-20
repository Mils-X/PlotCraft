"""Regresión no lineal dosis-respuesta de 4 parámetros (4PL).

Modelo (misma convención que GraphPad Prism, «log(agonista/inhibidor) vs. respuesta, pendiente variable»):

    Y = Bottom + (Top - Bottom) / (1 + 10^((LogIC50 - log10 X) * Hill))

Hill < 0 cuando la curva desciende con la dosis (inhibición) y Hill > 0 cuando sube.
IC50 es el IC50/EC50 *relativo*: la dosis que da la respuesta a mitad de camino entre Bottom y Top.
Los errores estándar y los IC son asintóticos (Wald, con la covarianza del Jacobiano) y el IC del IC50 se
obtiene transformando el IC de LogIC50. Cada réplica cuenta como un punto independiente.
"""
from __future__ import annotations

import html
import math
import warnings
from dataclasses import asdict, dataclass, field, fields

import numpy as np
from scipy import optimize, stats

from .xydata import XYData

PARAMS = ("bottom", "top", "logic50", "hill")
LABELS = {"bottom": "Bottom", "top": "Top", "hill": "Pendiente de Hill", "logic50": "LogIC50", "ic50": "IC50"}


def _pow10(v: float) -> float:
    """10**v sin desbordar: ±∞ si se sale de rango, NaN si no hay valor."""
    if math.isnan(v):
        return math.nan
    try:
        return 10.0 ** v
    except OverflowError:
        return math.inf if v > 0 else 0.0


def model(x, bottom, top, logic50, hill):
    x = np.asarray(x, dtype=float)
    expo = np.clip((logic50 - np.log10(x)) * hill, -300.0, 300.0)
    return bottom + (top - bottom) / (1.0 + 10.0 ** expo)


@dataclass
class FitConfig:
    fix_bottom: float | None = None
    fix_top: float | None = None
    fix_hill: float | None = None
    alpha: float = 0.05
    show_guides: bool = True
    active: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FitConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class FitParam:
    name: str
    value: float
    se: float = math.nan
    ci_low: float = math.nan
    ci_high: float = math.nan
    fixed: bool = False


@dataclass
class FitResult:
    series: str
    n: int
    excluded: int
    df: int
    sse: float
    r2: float
    sy_x: float
    alpha: float
    params: dict[str, FitParam]
    notes: list[str] = field(default_factory=list)

    @property
    def ic50(self) -> float:
        return self.params["ic50"].value

    def curve(self, x):
        p = self.params
        return model(x, p["bottom"].value, p["top"].value, p["logic50"].value, p["hill"].value)


@dataclass
class FitReport:
    results: dict[str, FitResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def _starts(lx, y, free, fixed, sign):
    """Puntos de partida: varias dosis medias y pendientes, para no quedar en un mínimo local."""
    lo, hi = float(np.min(y)), float(np.max(y))
    mid = (lo + hi) / 2
    doses = np.unique(lx)
    means = np.array([y[lx == d].mean() for d in doses])
    cross = [float(np.median(lx))]
    for i in range(len(doses) - 1):
        a, b = means[i] - mid, means[i + 1] - mid
        if a == 0 or a * b < 0:
            t = 0.0 if a == b else a / (a - b)
            cross.insert(0, float(doses[i] + t * (doses[i + 1] - doses[i])))
            break
    span = float(lx.max() - lx.min())
    cross += [float(lx.min() + 0.3 * span), float(lx.max() - 0.3 * span)]
    out = []
    for lg in cross:
        for h in (sign, 2 * sign, 0.5 * sign):
            base = {"bottom": lo, "top": hi, "logic50": lg, "hill": h}
            base.update({k: v for k, v in fixed.items() if v is not None})
            out.append([base[p] for p in free])
    return out


def fit_dose_response(x, y, cfg: FitConfig | None = None, series: str = "") -> FitResult:
    cfg = cfg or FitConfig()
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    excluded = int((ok & (x <= 0)).sum())
    ok &= x > 0
    x, y = x[ok], y[ok]
    fixed = {"bottom": cfg.fix_bottom, "top": cfg.fix_top, "hill": cfg.fix_hill}
    free = [p for p in PARAMS if fixed.get(p) is None]   # LogIC50 siempre es libre
    n = len(x)
    if len(np.unique(x)) < 3:
        raise ValueError("Se necesitan al menos 3 dosis distintas mayores que 0.")
    if n < len(free):
        raise ValueError(f"Se necesitan al menos {len(free)} puntos para estimar {len(free)} parámetros libres.")
    lx = np.log10(x)

    def f(xx, *p):
        d = dict(zip(free, p))
        d.update({k: v for k, v in fixed.items() if v is not None})
        return model(xx, d["bottom"], d["top"], d["logic50"], d["hill"])

    lo_b = {"bottom": -np.inf, "top": -np.inf, "logic50": float(lx.min()) - 2, "hill": -30.0}
    hi_b = {"bottom": np.inf, "top": np.inf, "logic50": float(lx.max()) + 2, "hill": 30.0}
    bounds = ([lo_b[p] for p in free], [hi_b[p] for p in free])
    corr = np.corrcoef(lx, y)[0, 1] if np.ptp(y) > 0 else 0.0
    sign = 1.0 if (np.isnan(corr) or corr >= 0) else -1.0

    best = None
    for p0 in _starts(lx, y, free, fixed, sign):
        try:
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore", optimize.OptimizeWarning)
                popt, pcov = optimize.curve_fit(f, x, y, p0=p0, bounds=bounds, maxfev=20000)
        except (RuntimeError, ValueError):
            continue
        sse = float(np.sum((y - f(x, *popt)) ** 2))
        if np.isfinite(sse) and (best is None or sse < best[0] - 1e-12 * max(1.0, best[0])):
            best = (sse, popt, pcov)
    if best is None:
        raise ValueError("El ajuste no convergió. Revisa los datos o fija algún parámetro (Bottom/Top).")
    sse, popt, pcov = best

    df = n - len(free)
    se = np.sqrt(np.diag(pcov)) if np.all(np.isfinite(pcov)) and df > 0 else np.full(len(free), math.nan)
    tcrit = float(stats.t.ppf(1 - cfg.alpha / 2, df)) if df > 0 else math.nan
    params: dict[str, FitParam] = {}
    values = dict(zip(free, popt))
    for p in PARAMS:
        if p in values:
            i = free.index(p)
            params[p] = FitParam(p, float(values[p]), float(se[i]), float(values[p] - tcrit * se[i]),
                                 float(values[p] + tcrit * se[i]))
        else:
            params[p] = FitParam(p, float(fixed[p]), fixed=True)
    lg = params["logic50"]
    params["ic50"] = FitParam("ic50", _pow10(lg.value), _pow10(lg.value) * math.log(10) * lg.se,
                              _pow10(lg.ci_low), _pow10(lg.ci_high))

    sst = float(np.sum((y - y.mean()) ** 2))
    res = FitResult(series, n, excluded, df, sse, 1 - sse / sst if sst > 0 else math.nan,
                    math.sqrt(sse / df) if df > 0 else math.nan, cfg.alpha, params)
    if excluded:
        res.notes.append(f"{excluded} punto(s) con dosis ≤ 0 se excluyeron del ajuste (el logaritmo no está definido).")
    if lg.value < lx.min() or lg.value > lx.max():
        res.notes.append("El IC50 estimado queda fuera del rango de dosis probadas: es una extrapolación, "
                         "interprétalo con mucha cautela.")
    if "hill" in values and abs(values["hill"]) > 29.9:
        res.notes.append("La pendiente de Hill llegó al límite (±30): los datos parecen un escalón; el ajuste es poco fiable.")
    if df <= 0:
        res.notes.append("No hay grados de libertad (tantos puntos como parámetros libres): no se pueden calcular EE ni IC.")
    elif math.isnan(lg.se) or math.isinf(lg.se):
        res.notes.append("No se pudieron calcular los intervalos de confianza: faltan puntos en las asíntotas o "
                         "los parámetros están mal determinados. Prueba a fijar Bottom y/o Top.")
    ic = params["ic50"]
    if not math.isnan(ic.ci_low) and (math.isinf(ic.ci_high) or ic.ci_low <= 0 or ic.ci_high / ic.ci_low > 100):
        res.notes.append("El IC del IC50 abarca más de 2 órdenes de magnitud (o es ilimitado): el IC50 está mal "
                         "determinado. Faltan dosis cerca del IC50 o hay demasiado ruido; fija Bottom/Top si procede.")
    return res


def fit_xy(xy: XYData, cfg: FitConfig | None = None) -> FitReport:
    """Ajusta cada serie Y por separado con todas sus réplicas como puntos independientes."""
    cfg = cfg or FitConfig()
    rep = FitReport()
    for name in xy.series:
        pts = xy.points(name)
        if not pts:
            continue
        try:
            rep.results[name] = fit_dose_response([p[0] for p in pts], [p[1] for p in pts], cfg, name)
        except (ValueError, ArithmeticError) as e:
            rep.errors[name] = str(e)
    if not rep.results and not rep.errors:
        rep.errors["—"] = "No hay datos. Pega la dosis en la columna X y las respuestas en las columnas Y."
    return rep


# ---------- formato ----------
def _n(v, nd=4):
    return "—" if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else f"{v:.{nd}g}"


def _ci(lo: float, hi: float) -> str:
    if math.isnan(lo) or math.isnan(hi):
        return "—"
    f = lambda v: "∞" if math.isinf(v) else _n(v)  # noqa: E731
    return f"{f(lo)} a {f(hi)}"


def fit_to_html(rep: FitReport, cfg: FitConfig) -> str:
    e = html.escape
    ci = f"IC{round((1 - cfg.alpha) * 100)}%"
    out = ["<h3>Dosis-respuesta — 4PL</h3>"]
    th = "style='text-align:left;padding:3px 10px;border-bottom:1px solid #888'"
    for name, r in rep.results.items():
        out.append(f"<h4>{e(name)}</h4><table cellspacing='0'><tr>"
                   + "".join(f"<th {th}>{h}</th>" for h in ("Parámetro", "Valor", "EE", ci)) + "</tr>")
        for key in ("bottom", "top", "hill", "logic50", "ic50"):
            p = r.params[key]
            if p.fixed:
                cells = [_n(p.value), "(fijo)", ""]
            else:
                cells = [_n(p.value), _n(p.se), _ci(p.ci_low, p.ci_high)]
            bold = ("<b>", "</b>") if key == "ic50" else ("", "")
            out.append("<tr>" + f"<td style='padding:3px 10px'>{bold[0]}{LABELS[key]}{bold[1]}</td>"
                       + "".join(f"<td style='padding:3px 10px'>{bold[0]}{c}{bold[1]}</td>" for c in cells) + "</tr>")
        out.append("</table>")
        out.append(f"<p>n = {r.n} · gl = {r.df} · R² = {_n(r.r2)} · Sy.x = {_n(r.sy_x)}</p>")
        out += [f"<p><i>{e(n)}</i></p>" for n in r.notes]
    for name, msg in rep.errors.items():
        out.append(f"<p style='color:#c0392b'><b>{e(name)}:</b> {e(msg)}</p>")
    out.append("<p><i>IC50 relativo: dosis a mitad de camino entre Bottom y Top. EE e IC asintóticos; el IC del IC50 "
               "se obtiene de transformar el IC de LogIC50. Pendiente de Hill negativa = la curva desciende.</i></p>")
    return "".join(out)
