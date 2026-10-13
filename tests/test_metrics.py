import copy

from rehoboam import geo, metrics, sim, state as st
from rehoboam.schemas import CityPlan, NearTermOutcome


def _base():
    s = st.load_state("sample", 0)
    return st.load_archive("sample"), {r.resident_id: r.prediction.model_copy(deep=True) for r in s.resident_states}


def _flat(preds, dev=0.1):
    out = {}
    for rid, p in preds.items():
        p = p.model_copy(deep=True)
        for e in p.life_path:
            e.p = 0.0
        for n in p.near_term:
            n.p = 1.0
        p.deviation_risk = dev
        out[rid] = p
    return out


def test_zero_variance_is_perfect_ring():
    archive, preds = _base()
    s = sim.initial_state(archive, _flat(preds), "t", 7)
    assert s.metrics.stability == 100.0
    assert s.metrics.variance_mean == 0.0
    assert s.divergences == []
    s1 = sim.begin_tick(s, [])
    plan = CityPlan(directive_summary="", cohort_policies=[], interventions=[],
                    projected_variance_before=0, projected_variance_after=0)
    assert sim.apply_plan(s1, plan) == []
    sim.finalize(s1, {})
    assert s1.divergences == []
    assert s1.metrics.stability == 100.0


def test_subject_variance_formula():
    _, preds = _base()
    p = _flat(preds)["r01"]
    assert metrics.subject_variance(p) == 0.0
    p.life_path[0].p = 0.5
    n = len(p.life_path) + len(p.near_term)
    assert abs(metrics.subject_variance(p) - 0.25 / n * (0.5 + p.deviation_risk)) < 1e-3


def test_reassigned_counted_as_zero_variance():
    s = st.load_state("sample", 2)
    m = metrics.compute_metrics(s)
    assert m.reassigned == 1 and m.active == 11 and m.total == 12
    vs = [0 if r.status == "reassigned" else metrics.subject_variance(r.prediction) for r in s.resident_states]
    assert abs(m.variance_mean - round(sum(vs) / 12, 4)) < 1e-9
    assert abs(m.stability - round(100 * (1 - sum(vs) / 12), 1)) < 1e-9


def test_brier_and_dissent():
    assert metrics.brier([]) is None
    r = [NearTermOutcome(pred_id="a", resident_id="r01", prediction="x", p=0.8, occurred=True),
         NearTermOutcome(pred_id="b", resident_id="r01", prediction="x", p=0.4, occurred=False)]
    assert abs(metrics.brier(r) - 0.1) < 1e-9
    s = st.load_state("sample", 1)
    dd = metrics.district_dissent(s)
    assert all(0 <= v <= 1 for v in dd.values())
    assert set(dd) == {d.district_id for d in s.city.districts}
    assert all(0 <= v <= 1 for v in metrics.cohort_dissent(s).values())


def test_divergence_geometry_matches_focal():
    s2 = copy.deepcopy(st.load_state("sample", 1))
    s2.divergences = metrics.compute_divergences(s2)
    assert s2.divergences
    for d in s2.divergences:
        assert d.angle_deg == s2.geo.resident_polar[d.focal_resident][0]
        assert d.place_label.endswith(", STILLWATER")
        assert d.focal_resident in d.resident_ids


def test_place_polar_inside_district_arcs():
    s = st.load_state("sample", 0)
    arcs = s.geo.district_arcs
    lm = {l.place_id: l for l in s.city.landmarks}
    for pid, (b, r) in s.geo.place_polar.items():
        if lm[pid].kind == "council":
            continue
        assert geo.bearing_in_arc(b, tuple(arcs[lm[pid].district_id]))
