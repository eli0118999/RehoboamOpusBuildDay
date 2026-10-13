import json
from pathlib import Path

import pytest

from rehoboam import archive as archive_mod
from rehoboam import config, llm, plan as plan_mod, predict as predict_mod
from rehoboam.schemas import (Archive, CityPlan, CityState, DeathForecast, Intervention, LifeEvent,
                              NearTerm, Prediction, Recommendation, ResidentState, RiskFactor)
from rehoboam.validate import validate_archive, validate_plan, validate_prediction

FIX = Path(__file__).parent / "fixtures" / "mini_archive.json"


@pytest.fixture
def archive():
    return Archive.model_validate_json(FIX.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def restore_llm():
    old = (llm._run_dir, llm._replay)
    yield
    llm._run_dir, llm._replay = old


def ev(i, year, ids, p=0.5):
    return LifeEvent(event_id=f"r01-e{i}", year=year, event="x", headline=f"H{i}", horizon_label="1 Year",
                     kind="career", p=p, evidence=ids)


def pred(rid="r01", life=None, death=None, cohort="stable-contributors", near=None, risks=None):
    life = life if life is not None else [ev(1, 2054, ["r01-0001"]), ev(2, 2056, ["r01-0002"])]
    return Prediction(
        resident_id=rid, cohort=cohort, life_path=life,
        death_forecast=death or DeathForecast(cause="Stroke", year=2080, age_at_death=68, confidence=0.4,
                                              evidence=["r01-0003"]),
        near_term=near or [NearTerm(pred_id="r01-t0-n1", prediction="p", p=0.5, evidence=["r01-0001"])],
        compliance_index=0.7, deviation_risk=0.3, dissent_signals=[], classification="II",
        overall_assessment="a", risk_factors=risks or [RiskFactor(factor="f", evidence=["r01-0001"])],
        recommendation=Recommendation(domain="Work", action="a"), assessment="b")


def rstate(rid="r01", status="active", floor=1, life=None):
    return ResidentState(resident_id=rid, status=status, escalation_floor=floor, current_district="d3",
                         prediction=pred(rid, life=life))


def iv(i, rid="r01", rung=1, **kw):
    d = dict(intervention_id=f"t1-i{i}", resident_id=rid, rung=rung, target_event_id=None, intent="suppress",
             place_id="p01", action="a", justification="j", citizen_story="s", evidence=["r01-0001"],
             p_success=0.6, disposition=None, cover_story=None)
    d.update(kw)
    return Intervention(**d)


def plan_of(*ivs):
    return CityPlan(directive_summary="d", cohort_policies=[], interventions=list(ivs),
                    projected_variance_before=0.5, projected_variance_after=0.3)


# ---------------------------------------------------------------- archive
def test_archive_fixture_clean(archive):
    _, warns = validate_archive(archive)
    assert warns == []


def test_archive_fixes(archive):
    a = archive.model_copy(deep=True)
    a.records.append(a.records[0].model_copy())                                  # duplicate id
    a.records.append(a.records[1].model_copy(update={"record_id": "r09-0001", "resident_id": "r09"}))
    a.records[2].place_id = "p99"
    a.residents[0].home_district = "d99"
    a.residents[1].home_place = "p99"
    a.residents[2].home_place = "p01"                                            # unhoused with a place
    a.relationships.append(a.relationships[0].model_copy(update={"b": "r77"}))
    fixed, warns = validate_archive(a)
    assert len({r.record_id for r in fixed.records}) == len(fixed.records) == 15
    assert fixed.records[2].place_id is None
    assert fixed.residents[0].home_district == "d1"
    assert fixed.residents[1].home_place is None
    assert fixed.residents[2].home_place is None
    assert len(fixed.relationships) == 3
    assert warns


def test_archive_structure_warnings(archive):
    a = archive.model_copy(deep=True)
    a.city.districts = a.city.districts[:3]
    a.city.landmarks = [p for p in a.city.landmarks if p.kind != "council"][:5]
    _, warns = validate_archive(a)
    joined = " ".join(warns)
    assert "council" in joined and "districts" in joined and "landmarks" in joined


# ---------------------------------------------------------------- prediction
def test_prediction_invalid_ids_and_ratio(archive):
    p = pred(life=[ev(1, 2054, ["r01-0001", "r01-9999"]), ev(2, 2056, ["nope"])],
             death=DeathForecast(cause="c", year=2080, age_at_death=68, confidence=0.4, evidence=["r01-0002"]))
    fixed, warns, ratio = validate_prediction(p, archive, "r01")
    # evidence: 2 + 1 + 1 (death) + 1 (near_term) + 1 (risk) = 6, invalid 2
    assert ratio == pytest.approx(2 / 6)
    assert fixed.life_path[0].evidence == ["r01-0001"]
    assert fixed.life_path[1].evidence == []


def test_prediction_clean_ratio_zero(archive):
    _, _, ratio = validate_prediction(pred(), archive, "r01")
    assert ratio == 0.0


def test_prediction_forces_rid_cohort_trims(archive):
    near = [NearTerm(pred_id=f"n{i}", prediction="p", p=0.5, evidence=[]) for i in range(7)]
    risks = [RiskFactor(factor=f"f{i}", evidence=[]) for i in range(6)]
    life = [ev(i, 2054 + i, []) for i in range(1, 12)]
    p = pred(rid="zzz", cohort="stable contributor", near=near, risks=risks, life=life,
             death=DeathForecast(cause="c", year=2090, age_at_death=68, confidence=0.4, evidence=[]))
    fixed, _, _ = validate_prediction(p, archive, "r01")
    assert fixed.resident_id == "r01"
    assert fixed.cohort == "stable-contributors"
    assert len(fixed.near_term) == 5 and len(fixed.risk_factors) == 4 and len(fixed.life_path) == 9
    p.cohort = "qqqqqqqqqq"
    assert validate_prediction(p, archive, "r01")[0].cohort in config.COHORTS


def test_prediction_years_monotonic(archive):
    life = [ev(1, 2060, []), ev(2, 2051, []), ev(3, 2055, [])]
    p = pred(life=life, death=DeathForecast(cause="c", year=2057, age_at_death=1, confidence=0.4, evidence=[]))
    fixed, _, _ = validate_prediction(p, archive, "r01")
    years = [e.year for e in fixed.life_path]
    assert years == sorted(years)
    assert years[0] >= archive.city.year
    assert fixed.death_forecast.year >= years[-1]
    assert fixed.death_forecast.age_at_death == 41 + (fixed.death_forecast.year - archive.city.year)


def test_prediction_unique_event_ids(archive):
    life = [ev(1, 2054, []), ev(1, 2055, [])]
    fixed, _, _ = validate_prediction(pred(life=life), archive, "r01")
    assert len({e.event_id for e in fixed.life_path}) == 2


# ---------------------------------------------------------------- plan
def test_plan_rung_floor_clamp_and_cap(archive):
    states = [rstate("r01", floor=3), rstate("r02", floor=5)]
    plan = plan_of(iv(1, "r01", rung=1), iv(2, "r02", rung=2, disposition="x", cover_story="y"))
    fixed, warns, _ = validate_plan(plan, archive, states)
    assert [i.rung for i in fixed.interventions] == [3, 5]
    assert fixed.interventions[1].disposition == "x"   # rung 5 keeps given values
    assert any("rung" in w for w in warns)
    # cap at 5
    p2 = plan_of(iv(1, "r01", rung=5, disposition="d", cover_story="c"))
    assert validate_plan(p2, archive, [rstate("r01", floor=9)])[0].interventions[0].rung == 5


def test_plan_rung5_fill_and_non5_null(archive):
    plan = plan_of(iv(1, "r01", rung=5), iv(2, "r02", rung=2, disposition="leak", cover_story="leak"))
    fixed, warns, _ = validate_plan(plan, archive, [rstate("r01"), rstate("r02")])
    a, b = fixed.interventions
    assert a.disposition and a.cover_story
    assert b.disposition is None and b.cover_story is None
    assert any("disposition" in w for w in warns)


def test_plan_drops_reassigned_and_unknown(archive):
    plan = plan_of(iv(1, "r01"), iv(2, "r02"), iv(3, "r99"))
    fixed, _, _ = validate_plan(plan, archive, [rstate("r01"), rstate("r02", status="reassigned")])
    assert [i.resident_id for i in fixed.interventions] == ["r01"]


def test_plan_one_per_resident_keeps_highest(archive):
    plan = plan_of(iv(1, "r01", rung=1), iv(2, "r01", rung=3), iv(3, "r01", rung=2))
    fixed, _, _ = validate_plan(plan, archive, [rstate("r01")])
    assert len(fixed.interventions) == 1 and fixed.interventions[0].rung == 3


def test_plan_places_events_evidence_policies(archive):
    from rehoboam.schemas import CohortPolicy
    life = [ev(1, 2054, [])]
    plan = plan_of(iv(1, "r01", place_id="p99", target_event_id="r01-e1", evidence=["r01-0001", "bad"]),
                   iv(2, "r02", target_event_id="r02-e9", evidence=["r01-0001"]))
    plan.cohort_policies = [CohortPolicy(policy_id="c1", cohort="elders", district_id="d99", kind="other",
                                         action="a", justification="j", citizen_story="s") for _ in range(2)]
    fixed, _, ratio = validate_plan(plan, archive, [rstate("r01", life=life), rstate("r02", life=life)])
    a, b = fixed.interventions
    assert a.place_id is None and a.target_event_id == "r01-e1" and a.evidence == ["r01-0001"]
    assert b.target_event_id is None
    assert ratio == pytest.approx(1 / 3)
    assert all(p.district_id is None for p in fixed.cohort_policies)
    assert len({p.policy_id for p in fixed.cohort_policies}) == 2


# ---------------------------------------------------------------- replay tests per pass
def _record(tmp_path, pass_name, key, obj):
    d = tmp_path / "calls"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pass_name}__{key}.json").write_text(json.dumps({"output": obj.model_dump(mode="json")}),
                                                encoding="utf-8")


def _spy(monkeypatch):
    calls = []
    real = llm.call

    def spy(pass_name, key, system, blocks, schema, effort="medium"):
        calls.append((pass_name, key, blocks, effort))
        return real(pass_name, key, system, blocks, schema, effort)

    monkeypatch.setattr(llm, "call", spy)
    return calls


def test_replay_archive(tmp_path, monkeypatch, archive):
    bad = archive.model_copy(deep=True)
    bad.records[0].place_id = "p99"
    _record(tmp_path, "archive", "seed", bad)
    llm.configure(tmp_path, replay=True)
    calls = _spy(monkeypatch)
    out = archive_mod.generate_archive(3, 2053)
    assert [c[:2] for c in calls] == [("archive", "seed")]
    assert out.records[0].place_id is None
    assert len(out.residents) == 3


def test_replay_predict_and_retry(tmp_path, monkeypatch, archive):
    _record(tmp_path, "predict", "t00_r01", pred(life=[ev(1, 2054, ["x1", "x2"])]))
    _record(tmp_path, "predict", "t00_r01_retry", pred())
    _record(tmp_path, "predict", "t00_r02", pred("r02"))
    llm.configure(tmp_path, replay=True)
    calls = _spy(monkeypatch)
    out = predict_mod.predict_many(archive, ["r01", "r02"], 0)
    assert set(out) == {"r01", "r02"}
    keys = [c[1] for c in calls]
    assert keys[0] == "t00_r01" and "t00_r01_retry" in keys and "t00_r02" in keys
    assert all(c[0] == "predict" for c in calls)
    assert out["r01"].life_path[0].evidence == ["r01-0001"]  # the retry won
    # cache prefix: archive block identical across subjects
    assert calls[0][2][0] == [c for c in calls if c[1] == "t00_r02"][0][2][0]
    retry = [c for c in calls if c[1].endswith("_retry")][0]
    assert "x1" in retry[2][-1]["text"]


def test_predict_blocks_recompute_and_interventions(tmp_path, monkeypatch, archive):
    _record(tmp_path, "predict", "t03_r01", pred())
    llm.configure(tmp_path, replay=True)
    calls = _spy(monkeypatch)
    rs = rstate("r01")
    rs.recompute_pending = True
    rs.deviation_note = "skipped shift"
    rs.current_place = "p07"
    rs.interventions_applied = [iv(1, rung=2, target_event_id="r01-e1")]
    predict_mod.predict_one(archive, "r01", 3, rs)
    task = calls[0][2][1]["text"]
    assert calls[0][3] == config.EFFORT["recompute"]
    assert "skipped shift" in task and "Narrow" in task and "Halvorsen Components (p07)" in task
    assert calls[0][2][0]["cache_control"]


def test_replay_plan(tmp_path, monkeypatch, archive):
    ticks = json.loads(config.SAMPLE_STATE.read_text(encoding="utf-8"))["ticks"]
    state = CityState.model_validate(ticks[1])
    rids = [r.resident_id for r in state.resident_states if r.status == "active"]
    _record(tmp_path, "plan", f"t{state.tick:02d}", plan_of(iv(1, rids[0], rung=1, place_id=None, evidence=[])))
    llm.configure(tmp_path, replay=True)
    calls = _spy(monkeypatch)
    out = plan_mod.make_plan(state)
    assert [c[:2] for c in calls] == [("plan", f"t{state.tick:02d}")]
    assert len(out.interventions) == 1
    task = calls[0][2][1]["text"]
    assert rids[0] in task
    assert predict_mod.archive_json(predict_mod.archive_of(state)) in calls[0][2][0]["text"]
