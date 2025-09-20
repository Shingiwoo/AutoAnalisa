from __future__ import annotations
from pydantic import BaseModel, validator
from typing import List


class SpotPlanLLM(BaseModel):
    mode: str
    entries: List[float]
    weights: List[float]
    tp: List[float]
    invalid: float

    @validator("weights")
    def _sum1(cls, v):
        s = round(sum(v), 6)
        assert 0.99 <= s <= 1.01, "weights must sum to 1"
        return v

    @validator("tp")
    def _ascending(cls, v, values):
        assert all(v[i] < v[i+1] for i in range(len(v)-1)), "tp must be ascending"
        if "entries" in values and values.get("entries"):
            assert min(values["entries"]) < v[0], "entry must be below tp1"
        return v

    @validator("invalid")
    def _invalid_lt_entry(cls, inv, values):
        if "entries" in values and values.get("entries"):
            assert inv < min(values["entries"]), "invalid must be below all entries"
        return inv

