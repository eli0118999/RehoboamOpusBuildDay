import json
from pathlib import Path

from rehoboam import config
from rehoboam.schemas import Archive, CityPlan, CityState, Prediction

FIX = Path(__file__).parent / "fixtures" / "mini_archive.json"


def test_archive_roundtrip():
    a = Archive.model_validate_json(FIX.read_text(encoding="utf-8"))
    assert len(a.residents) == 3
    assert Archive.model_validate_json(a.model_dump_json()) == a
    assert Archive.model_validate(json.loads(a.model_dump_json())) == a


def test_prediction_and_plan_roundtrip():
    ticks = json.loads(config.SAMPLE_STATE.read_text(encoding="utf-8"))["ticks"]
    st = CityState.model_validate(ticks[0])
    p = st.resident_states[0].prediction
    assert Prediction.model_validate_json(p.model_dump_json()) == p
    plan = CityState.model_validate(ticks[1]).plan
    assert plan is not None
    assert CityPlan.model_validate_json(plan.model_dump_json()) == plan


def test_sample_state_ticks_validate():
    data = json.loads(config.SAMPLE_STATE.read_text(encoding="utf-8"))
    assert len(data["ticks"]) >= 3
    for t in data["ticks"]:
        st = CityState.model_validate(t)
        assert CityState.model_validate_json(st.model_dump_json()) == st


def test_json_schemas_build():
    for m in (Archive, Prediction, CityPlan):
        assert m.model_json_schema()["type"] == "object"
