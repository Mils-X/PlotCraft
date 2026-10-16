"""Estadística descriptiva básica."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import stats

ERROR_TYPES = ("SEM", "SD", "IC95")


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    error: float


def summarize(values: Iterable[float], error_type: str = "SEM") -> Summary:
    """Media y error de un grupo. SD con ddof=1; IC95 con t de Student."""
    if error_type not in ERROR_TYPES:
        raise ValueError(f"error_type debe ser uno de {ERROR_TYPES}")
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
