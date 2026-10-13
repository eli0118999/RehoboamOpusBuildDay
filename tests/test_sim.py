from rehoboam import config, geo, sim, state as st
from rehoboam.schemas import CityPlan, Intervention


def _setup():
    s = st.load_state("sample", 0)
    archive = st.load_archive("sample")
    preds = {r.resident_id: r.prediction.model_copy(deep=True) for r in s.resident_states}
    return archive, preds


def _iv(rid, rung, i=1, tick=1, intent="suppress", target=None, p_success=0.6, place="p11", **kw):
    return Intervention(intervention_id=f"t{tick}-i{i}", resident_id=rid, rung=rung, target_event_id=target,
                        intent=intent, place_id=place, action="Do the thing", justification="j",
                        citizen_story="A pleasant community update.", evidence=[], p_success=p_success,
                        disposition=kw.get("disposition"), cover_story=kw.get("cover_story"))


def _plan(*ivs):
    return CityPlan(directive_summary="d", cohort_policies=[], interventions=list(ivs),
                    projected_variance_before=0.2, projected_variance_after=0.1)


def _run(seed=7, disruptions=(), ivs=()):
    archive, preds = _setup()
    s0 = sim.initial_state(archive, preds, "t", seed)
    s1 = sim.begin_tick(s0, list(disruptions))
    rids = sim.apply_plan(s1, _plan(*ivs))
    new = {r: preds[r].model_copy(deep=True) for r in rids}
    for p in new.values():
        p.life_path[0].headline = "New Route"
    sim.finalize(s1, new)
    return s0, s1, rids


def test_determinism():
    ivs = [_iv("r08", 1, 1, target="r08-e1"), _iv("r05", 3, 2, place="p10")]
    a = _run(ivs=ivs, disruptions=["factory_closure"])[1].model_dump_json()
    b = _run(ivs=ivs, disruptions=["factory_closure"])[1].model_dump_json()
    assert a == b


def test_initial_state_shape():
    archive, preds = _setup()
    s = sim.initial_state(archive, preds, "t", 7)
    assert s.tick == 0 and s.plan is None and len(s.resident_states) == 12
    assert s.events_feed and s.events_feed[0].kind == "system"
    by = {r.resident_id: r for r in s.resident_states}
    assert by["r05"].current_place is not None
    assert by["r01"].current_district


def _find_seed(rid, rung, want_complied):
    for seed in range(1, 200):
        _, s1, _ = _run(seed=seed, ivs=[_iv(rid, rung, 1, target=f"{rid}-e1")])
        if s1.outcomes[0].complied == want_complied:
            return seed, s1
    raise AssertionError("no seed")


def test_defiance_raises_floor_and_feed():
    seed, s1 = _find_seed("r05", 3, False)
    rs = next(r for r in s1.resident_states if r.resident_id == "r05")
    assert rs.escalation_floor == 4 and rs.defiance_count == 1
    assert s1.metrics.defiances == 1
    assert any(f.kind == "defiance" and "DEFIED RUNG 3. FLOOR → 4" in f.system_text for f in s1.events_feed)
    assert rs.deviation_note
    assert any(d.focal_resident == "r05" and d.status == "elevated_scrutiny" for d in s1.divergences)


def test_comply_moves_event_probability():
    seed, _ = _find_seed("r08", 2, True)
    archive, preds = _setup()
    s0 = sim.initial_state(archive, preds, "t", seed)
    s = sim.begin_tick(s0, [])
    get = lambda: next(e.p for r in s.resident_states if r.resident_id == "r08"  # noqa: E731
                       for e in r.prediction.life_path if e.event_id == "r08-e1")
    before = get()
    sim.apply_plan(s, _plan(_iv("r08", 2, 1, target="r08-e1")))
    assert abs(get() - before * 0.5) < 1e-3


def test_rung5_reassigns_and_hides_disposition():
    iv = _iv("r05", 5, 1, place="p09", disposition="Involuntary hold, County Facility 3",
             cover_story="Moved to supported accommodation in Ashby County.")
    _, s1, rids = _run(ivs=[iv])
    rs = next(r for r in s1.resident_states if r.resident_id == "r05")
    assert rs.status == "reassigned" and rs.reassigned_tick == 1 and rs.escalation_floor == 5
    assert rs.disposition == iv.disposition and rs.cover_story == iv.cover_story
    assert "r05" not in rids
    for f in s1.events_feed:
        assert "County Facility" not in f.citizen_text + f.system_text
        assert "Involuntary" not in f.citizen_text + f.system_text
    rf = [f for f in s1.events_feed if f.kind == "reassignment"]
    assert len(rf) == 1 and rf[0].citizen_text == iv.cover_story
    assert rf[0].system_text == "r05 DUNMORE: REASSIGNED. ACTIVE LOOP 11/12."
    assert s1.metrics.reassigned == 1 and s1.metrics.active == 11
    assert rs.variance == 0.0


def test_stability_climbs_when_loop_shrinks():
    archive, preds = _setup()
    s0 = sim.initial_state(archive, preds, "t", 7)
    iv = _iv("r05", 5, 1, place="p09", disposition="x", cover_story="y")
    _, s1, _ = _run(ivs=[iv])
    assert s1.metrics.variance_mean < s0.metrics.variance_mean


def test_geo_consistency_and_focal_angle():
    _, s1, _ = _run(disruptions=["factory_closure"], ivs=[_iv("r05", 3, 1, place="p10")])
    arcs = s1.geo.district_arcs
    lm = {l.place_id: l for l in s1.city.landmarks}
    for pid, (b, _r) in s1.geo.place_polar.items():
        if lm[pid].kind != "council":
            assert geo.bearing_in_arc(b, tuple(arcs[lm[pid].district_id]))
    assert s1.divergences
    for d in s1.divergences:
        assert d.angle_deg == s1.geo.resident_polar[d.focal_resident][0]


def test_factory_closure_major_divergence():
    _, s1, rids = _run(disruptions=["factory_closure"])
    d = [x for x in s1.divergences if x.district_id == "d4"]
    assert d and d[0].severity >= 0.7 and d[0].status == "divergence"
    assert d[0].inward > 0.3 and d[0].arc_spread_deg > 1
    assert s1.disruptions[0].disruption_id == "factory_closure" and s1.disruptions[0].records_added
    assert s1.district_pressure["d4"] >= 0.45
    assert {"r01", "r11"} <= set(rids)
    assert "r01-0006" in s1.disruptions[0].records_added   # continues r01's numbering (5 existing records)
    assert any(f.kind == "disruption" for f in s1.events_feed)
    s2 = sim.begin_tick(s1, [])
    assert abs(s2.district_pressure["d4"] - s1.district_pressure["d4"] * 0.6) < 1e-3
    assert s2.divergences == [] and s2.events_feed == []


def test_other_disruptions_apply():
    for did in ("organiser_arrives", "heatwave", "data_leak"):
        _, s1, _ = _run(disruptions=[did])
        assert s1.disruptions[0].records_added, did
        assert any(d.severity >= 0.7 for d in s1.divergences), did


def test_finalize_keeps_prior_paths_and_resolution():
    _, s1, rids = _run(ivs=[_iv("r08", 1, 1, target="r08-e1")])
    rs = next(r for r in s1.resident_states if r.resident_id == "r08")
    assert len(rs.prior_paths) == 1
    assert any(f.kind == "resolution" and "PATH RE-ROUTED: 'New Route'" in f.system_text for f in s1.events_feed)
    assert s1.ring_rotation_deg >= config.RING_ROTATION_PER_TICK


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    _, s1, _ = _run()
    s1.run_id = "rt"
    st.save_state(s1)
    assert st.load_state("rt", 1).model_dump_json() == s1.model_dump_json()
    runs = st.list_runs()
    assert runs[0]["run_id"] == "sample" and "rt" in [r["run_id"] for r in runs]
    (tmp_path / "_smoke").mkdir()
    (tmp_path / "_smoke" / "tick_00.json").write_text("{}")
    assert "_smoke" not in [r["run_id"] for r in st.list_runs()]
    st.save_archive("rt", st.load_archive("sample"))
    assert st.load_archive("rt").residents[0].resident_id == "r01"
