"""Estadística descriptiva básica."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import stats

ERROR_TYPES = ("SEM", "SD", "IC95", "Mediana ± RIQ")
_PARAMETRIC = ("SEM", "SD", "IC95")


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    error: float


def summarize(values: Iterable[float], error_type: str = "SEM") -> Summary:
    """Media y error de un grupo. SD con ddof=1; IC95 con t de Student."""
    if error_type not in _PARAMETRIC:
        raise ValueError(f"error_type debe ser uno de {_PARAMETRIC}")
    arr = np.asarray([v for v in values if v is not None and not math.isnan(v)], dtype=float)
    n = arr.size
    if n == 0:
        return Summary(0, math.nan, math.nan)
    mean = float(arr.mean())
    if n == 1:
        return Summary(1, mean, 0.0)
    sd = float(arr.std(ddof=1))
    sem = sd / math.sqrt(n)
    if error_type == "SD":
        err = sd
    elif error_type == "SEM":
        err = sem
    else:
        err = float(stats.t.ppf(0.975, n - 1)) * sem
    return Summary(n, mean, err)


def center_and_error(values: Iterable[float], error_type: str = "SEM") -> tuple[float, float, float]:
    """(centro, error_inferior, error_superior). Media ± error, o mediana con cuartiles (RIQ)."""
    if error_type == "Mediana ± RIQ":
        arr = np.asarray([v for v in values if v is not None and not math.isnan(v)], dtype=float)
        if arr.size == 0:
            return math.nan, math.nan, math.nan
        med = float(np.median(arr))
        q1, q3 = (float(x) for x in np.percentile(arr, [25, 75]))
        return med, med - q1, q3 - med
    s = summarize(values, error_type)
    return s.mean, s.error, s.error
