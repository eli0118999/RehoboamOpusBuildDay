"""Metrics, dissent and divergences (what the Rehoboam circle draws). Pure functions of CityState."""
from . import config, geo
from .schemas import CityState, Divergence, Metrics, NearTermOutcome, Prediction

ANALYSIS_MARK = "ANALYSIS REQUIRED"   # sim.py writes this into the system_text of spontaneous-deviation feed items
THRESHOLD = 0.15                      # below this a signal is noise: the ring stays a hairline


def subject_variance(p: Prediction) -> float:
    ps = [e.p for e in p.life_path] + [n.p for n in p.near_term]
    if not ps:
        return 0.0
    return round(sum(x * (1 - x) for x in ps) / len(ps) * (0.5 + p.deviation_risk), 4)


def _vars(state: CityState) -> list[float]:
    return [0.0 if s.status == "reassigned" else subject_variance(s.prediction) for s in state.resident_states]


def brier(results: list[NearTermOutcome]) -> float | None:
    if not results:
        return None
    return round(sum((o.p - (1.0 if o.occurred else 0.0)) ** 2 for o in results) / len(results), 4)


def compute_metrics(state: CityState) -> Metrics:
    vs = _vars(state)
    mean = sum(vs) / len(vs) if vs else 0.0
    active = sum(s.status == "active" for s in state.resident_states)
    b = brier(state.near_term_results)
    return Metrics(
        stability=round(100 * (1 - mean), 1), variance_mean=round(mean, 4),
        accuracy=None if b is None else round(1 - b, 3), brier=b, active=active,
        total=len(state.resident_states), reassigned=len(state.resident_states) - active,
        interventions=len(state.outcomes), defiances=sum(not o.complied for o in state.outcomes))


def district_dissent(state: CityState) -> dict[str, float]:
    out = {}
    for d in state.city.districts:
        here = [s.prediction.deviation_risk for s in state.resident_states
                if s.current_district == d.district_id and s.status == "active"]
        base = sum(here) / len(here) if here else 0.1
        out[d.district_id] = round(min(1.0, max(0.0, base + state.district_pressure.get(d.district_id, 0.0))), 3)
    return out


def cohort_dissent(state: CityState) -> dict[str, float]:
    out = {}
    for c in config.COHORTS:
        m = [s for s in state.resident_states if s.prediction.cohort == c and s.status == "active"]
        if m:
            dev = sum(s.prediction.deviation_risk for s in m) / len(m)
            dens = sum(len(s.prediction.dissent_signals) for s in m) / len(m)
            out[c] = round(min(1.0, max(0.0, dev + 0.05 * dens)), 3)
    return out


# ---------------------------------------------------------------- divergences
def affected_by_disruption(state: CityState, ev) -> list[str]:
    owners = {r.record_id: r.resident_id for r in state.records}
    seen = []
    for rec_id in ev.records_added:
        o = owners.get(rec_id)
        if o and o not in seen:
            seen.append(o)
    return seen


def _tier_cap(max_sev: float) -> float:
    return 0.449 if max_sev < 0.45 else 0.699 if max_sev < 0.7 else 1.0


def _signals(state: CityState) -> dict[str, dict]:
    """resident_id -> strongest signal {status, sev, district, kind, rung?, low_p?}."""
    rs_by = {s.resident_id: s for s in state.resident_states}
    ivs = {i.intervention_id: i for i in (state.plan.interventions if state.plan else [])}
    sig: dict[str, dict] = {}

    def put(rid, status, sev, district, **kw):
        s = rs_by.get(rid)
        if s is None or s.status != "active":
            return
        if rid not in sig or sev > sig[rid]["sev"]:
            sig[rid] = dict(status=status, sev=sev, district=district or s.current_district, **kw)

    for ev in state.disruptions:
        pr = state.district_pressure.get(ev.district_id, 0.0) if ev.district_id else 0.2
        sev = min(1.0, 0.72 + 0.28 * min(1.0, pr / 0.45))
        for rid in affected_by_disruption(state, ev):
            s = rs_by.get(rid)
            if s is not None:
                put(rid, "divergence", sev, ev.district_id or s.current_district, kind="disruption")
    for o in state.outcomes:
        s = rs_by.get(o.resident_id)
        if s is None or o.rung >= 5:
            continue
        iv = ivs.get(o.intervention_id)
        dev = s.prediction.deviation_risk
        low_p = iv is not None and iv.p_success < 0.4
        if not o.complied:
            if o.rung <= 2:
                sev = min(0.449, 0.18 + 0.08 * o.rung + 0.12 * dev)
                put(o.resident_id, "divergence", sev, None, kind="defiance", rung=o.rung, low_p=low_p)
            else:
                sev = min(0.699, max(0.45, 0.4 + 0.05 * o.rung + 0.1 * dev))
                put(o.resident_id, "elevated_scrutiny", sev, None, kind="defiance", rung=o.rung, low_p=low_p)
        elif dev >= 0.5 or o.rung >= 3 or low_p:
            sev = min(0.699, 0.45 + 0.2 * dev + 0.02 * o.rung)
            put(o.resident_id, "special_circumstances", sev, None, kind="complied", rung=o.rung, low_p=low_p)
    for it in state.events_feed:
        if it.kind == "prediction" and it.resident_id and ANALYSIS_MARK in it.system_text:
            s = rs_by.get(it.resident_id)
            if s:
                put(it.resident_id, "analysis_required", min(0.35, 0.2 + 0.15 * s.prediction.deviation_risk),
                    None, kind="spontaneous")
    for s in state.resident_states:
        if s.status == "active" and s.recompute_pending and s.defiance_count > 0 and s.resident_id not in sig:
            put(s.resident_id, "elevated_scrutiny", 0.45, None, kind="pending")
    if state.tick == 0 and state.plan is None and not sig:
        act = [s for s in state.resident_states if s.status == "active"]
        if act:
            top = max(act, key=lambda s: (s.prediction.deviation_risk, s.resident_id))
            if top.prediction.deviation_risk >= 0.6:
                put(top.resident_id, "analysis_required", min(0.3, 0.2 + 0.1 * top.prediction.deviation_risk),
                    None, kind="baseline")
    return {r: v for r, v in sig.items() if v["sev"] >= THRESHOLD}


def compute_divergences(state: CityState) -> list[Divergence]:
    sig = _signals(state)
    if not sig:
        return []
    rs_by = {s.resident_id: s for s in state.resident_states}
    dname = {d.district_id: d.name for d in state.city.districts}
    groups: dict[str, list[str]] = {}
    for rid, v in sig.items():
        groups.setdefault(v["district"], []).append(rid)
    out = []
    for did in sorted(groups):
        rids = sorted(groups[did])

        def keyf(r, did=did):
            return (sig[r]["sev"], rs_by[r].current_district == did, rs_by[r].prediction.deviation_risk, r)
        focal = max(rids, key=keyf)
        top = sig[focal]
        # relationship reach: strong ties of signal subjects get pulled into the divergence
        added, reach, contagion = [], 0.0, 0.0
        for rel in state.relationships:
            for a, b in ((rel.a, rel.b), (rel.b, rel.a)):
                if a in rids and b in rs_by and rs_by[b].status == "active" and b not in rids:
                    if rel.strength >= 0.4:
                        if b not in added:
                            added.append(b)
                        reach += rel.strength
                    if rs_by[b].prediction.deviation_risk >= 0.5:
                        contagion += rel.strength * rs_by[b].prediction.deviation_risk
        members = sorted(set(rids) | set(added))
        n = len(rids)
        sev = round(min(_tier_cap(top["sev"]), top["sev"] + 0.03 * (n - 1)), 3)
        outward = round(min(1.0, sev + 0.05 * (n - 1) + 0.02 * len(added)), 3)
        inward = 0.05
        if any(sig[r].get("kind") == "disruption" for r in rids):
            inward += 0.3
        if any(sig[r].get("kind") == "defiance" and (sig[r].get("rung") or 0) >= 3 for r in rids):
            inward += 0.3
        if any(sig[r].get("low_p") for r in rids):
            inward += 0.2
        inward += 0.25 * min(1.0, contagion)
        inward = round(min(1.0, inward), 3)
        concentrated = n == 1 and not added
        spread = 0.04 if concentrated else round(0.04 + 1.6 * (n - 1) + 2.0 * reach, 2)
        b, r = state.geo.resident_polar[focal]
        out.append(Divergence(
            divergence_id=f"{did}-{focal}-{top['status']}", status=top["status"], district_id=did,
            focal_resident=focal, focal_coords=geo.coords(b, r), angle_deg=b, arc_spread_deg=spread,
            outward=outward, inward=inward, severity=sev, resident_ids=members,
            place_label=f"{dname.get(did, did).upper()}, {state.city.name.upper()}",
            spread_label=geo.spread_label(spread, concentrated)))
    out.sort(key=lambda d: (-d.severity, d.divergence_id))
    return out
