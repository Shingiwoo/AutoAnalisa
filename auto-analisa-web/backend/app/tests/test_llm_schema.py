import json
import pytest
from app.services.llm_parser import SpotPlanLLM


def test_schema_ok():
    raw = json.dumps({
        "mode": "PB", "entries": [1.0, 0.99], "weights": [0.4, 0.6], "tp": [1.02, 1.04], "invalid": 0.985
    })
    obj = SpotPlanLLM.parse_raw(raw)
    assert obj.mode == 'PB'


@pytest.mark.parametrize("bad", [
    {"mode": "PB", "entries": [1.0], "weights": [1.2], "tp": [1.01, 1.02], "invalid": 0.99},
    {"mode": "PB", "entries": [1.0, 0.99], "weights": [0.3, 0.3], "tp": [1.02, 1.01], "invalid": 0.985},
    {"mode": "PB", "entries": [1.0, 0.99], "weights": [0.4, 0.6], "tp": [0.98, 1.02], "invalid": 0.985},
])
def test_schema_fail(bad):
    with pytest.raises(Exception):
        SpotPlanLLM.parse_obj(bad)

