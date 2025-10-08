from __future__ import annotations

from typing import Dict


def weighted_avg(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    wsum = float(sum(weights.values()) or 1.0)
    return float(sum(float(weights.get(k, 0.0)) * float(scores.get(k, 0.0)) for k in weights) / wsum)


def bucket_strength(x: float) -> str:
    ax = abs(float(x))
    if ax < 0.20:
        return "NONE"
    if ax < 0.35:
        return "WEAK"
    if ax < 0.55:
        return "MEDIUM"
    if ax < 0.75:
        return "STRONG"
    return "EXTREME"


class EmaSmoother:
    def __init__(self, alpha: float = 0.3):
        self.alpha = float(alpha)
        self._y = None

    def update(self, x: float) -> float:
        xv = float(x)
        if self._y is None:
            self._y = xv
        else:
            self._y = self.alpha * xv + (1.0 - self.alpha) * self._y
        return float(self._y)

