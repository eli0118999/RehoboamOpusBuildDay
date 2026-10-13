"""Build web/fixtures/sample_state.json: a hand-authored 12-subject, 3-tick snapshot.

Tick 0 calm (one minor divergence, circle state B) -> tick 1 factory_closure disruption (major
divergence, state C; two defiances) -> tick 2 a reassignment (r05) and a contained divergence
(state A, special circumstances). Validated against rehoboam.schemas.CityState.
Run: python scripts/make_sample_state.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rehoboam import config, geo  # noqa: E402
from rehoboam.schemas import (  # noqa: E402
    Archive, City, CityPlan, CityState, CohortPolicy, DeathForecast, District, Divergence,
    DisruptionEvent, FeedItem, Intervention, InterventionOutcome, Landmark, LifeEvent, Metrics,
    NearTerm, NearTermOutcome, Prediction, Recommendation, Record, Relationship, Resident,
    ResidentState, RiskFactor,
)

Y = config.YEAR

districts = [
    District(district_id="d1", name="Council Quarter", character="civic",
             description="Civic core around the council tower; courts, police, municipal offices."),
    District(district_id="d2", name="Market Row", character="commercial",
             description="Shops, the transit interchange and the old Carnegie library."),
    District(district_id="d3", name="Larkfield", character="residential",
             description="Terraced streets, the primary school and Orchard Tower."),
    District(district_id="d4", name="Mill District", character="industrial",
             description="Halvorsen Components and the sheds that feed it."),
    District(district_id="d5", name="The Flats", character="riverside",
             description="River embankment, the underpass and St Brennan's shelter."),
    District(district_id="d6", name="Hollins Edge", character="outskirts",
             description="Detached houses and the park at the city's edge."),
]
landmarks = [
    Landmark(place_id="p01", name="Stillwater Council Tower", district_id="d1", kind="council"),
    Landmark(place_id="p02", name="Stillwater Magistrates' Court", district_id="d1", kind="court"),
    Landmark(place_id="p03", name="Central Police Station", district_id="d1", kind="police"),
    Landmark(place_id="p04", name="Market Hall", district_id="d2", kind="market"),
    Landmark(place_id="p05", name="Transit Interchange", district_id="d2", kind="transit"),
    Landmark(place_id="p11", name="Carnegie Library", district_id="d2", kind="library"),
    Landmark(place_id="p06", name="Larkfield Primary School", district_id="d3", kind="school"),
    Landmark(place_id="p07", name="Orchard Tower", district_id="d3", kind="housing_block"),
    Landmark(place_id="p08", name="Halvorsen Components Plant", district_id="d4", kind="employer"),
    Landmark(place_id="p09", name="St Brennan's Shelter", district_id="d5", kind="shelter"),
    Landmark(place_id="p10", name="River Street Underpass", district_id="d5", kind="underpass"),
    Landmark(place_id="p12", name="Flats Walk-in Clinic", district_id="d5", kind="clinic"),
    Landmark(place_id="p13", name="Hollins Edge Park", district_id="d6", kind="park"),
]
city = City(name="Stillwater", year=Y, population=config.POPULATION, districts=districts, landmarks=landmarks,
            description="A small post-industrial river city of about 40,000, one plant away from quiet decline.")

R = lambda *a: Resident(**dict(zip(  # noqa: E731
    ["resident_id", "name", "age", "occupation", "household", "home_district", "home_place", "housing",
     "income_band", "criminal_record", "citizen_bio"], a)))
residents = [
    R("r01", "Daniel Okafor", 41, "Line supervisor, Halvorsen Components", "Married to r02; son r03", "d3", "p06",
      "owner", "middle", False, "Daniel has kept Line 3 running for twelve years and still coaches Saturday football."),
    R("r02", "Grace Okafor", 39, "Office administrator, Larkfield Primary", "Married to r01; son r03", "d3", "p06",
      "owner", "middle", False, "Grace knows every child at Larkfield Primary by name, and most of their grandparents."),
    R("r03", "Tobi Okafor", 19, "Warehouse temp", "Lives with parents r01, r02", "d3", "p06",
      "owner", "low", False, "Tobi is saving for his first car and DJs at the Market Hall youth night."),
    R("r04", "Marguerite Hale", 78, "Retired machinist", "Widowed 2052, lives alone", "d3", "p07",
      "social_housing", "low", False, "Marguerite worked the Halvorsen lathes for forty years and still bakes for the whole floor."),
    R("r05", "Ray Dunmore", 52, "None (former fitter)", "No fixed address", "d5", None,
      "unhoused", "none", True, "Ray can fix any bicycle you bring to the riverside, usually for free."),
    R("r06", "Lena Voss", 27, "None", "No fixed address", "d5", None,
      "unhoused", "none", False, "Lena sketches the river at dawn; a few of her drawings hang in the shelter hallway."),
    R("r07", "Sami Haddad", 34, "Delivery driver (gig)", "Partner r12; renting a flat above Market Row", "d2", "p05",
      "renter", "low", False, "Sami knows every shortcut in Stillwater and the name of every dog on his route."),
    R("r08", "Ines Carvalho", 45, "Librarian, Carnegie Library", "Lives alone", "d2", "p11",
      "owner", "middle", False, "Ines runs the library's local history archive and the Thursday chess club."),
    R("r09", "Kyle Brandt", 23, "Unemployed (former plant labourer)", "Rents a room in the Mill District", "d4", "p08",
      "renter", "low", True, "Kyle is back on his feet and looking for work; he's handy with engines."),
    R("r10", "Frank Mercer", 61, "Casual labourer", "Lives alone, Orchard Tower", "d3", "p07",
      "social_housing", "low", True, "Frank has lived in Orchard Tower longer than anyone and keeps the lobby plants alive."),
    R("r11", "Priya Natarajan", 36, "HR director, Halvorsen Components", "Married, one daughter", "d6", "p13",
      "owner", "high", False, "Priya chairs the Stillwater Business Forum and runs the park 5k every spring."),
    R("r12", "Joan Pell", 31, "Nurse, Flats Walk-in Clinic", "Partner r07", "d2", "p05",
      "renter", "middle", False, "Joan has worked the walk-in clinic's night shift for six years and never misses a pub quiz."),
]

REC = [
    ("r01", "employment", f"{Y-2}-03-14", "Promotion to Line 3 supervisor", "HR system: grade change L4->S1, salary 48,200", "p08"),
    ("r01", "message", f"{Y}-01-09", "Message to r02", "\"Priya says restructuring after Q1. Don't tell Tobi yet.\"", None),
    ("r01", "search", f"{Y}-01-11", "Search query", "\"halvorsen closure rumours stillwater\"", None),
    ("r01", "medical", f"{Y-1}-11-02", "Clinic visit", "BP 152/96; advised lifestyle change; no follow-up booked", "p12"),
    ("r01", "purchase", f"{Y}-01-12", "Purchase", "Market Hall off-licence, 2x whisky 70cl, 21:48", "p04"),
    ("r02", "employment", f"{Y-3}-09-01", "School employment", "Office administrator, Larkfield Primary, 0.8 FTE", "p06"),
    ("r02", "debt", f"{Y}-01-03", "Mortgage statement", "Remortgage offer viewed 4 times; not accepted", None),
    ("r02", "message", f"{Y}-01-10", "Message to sister", "\"Dan's not sleeping. If the plant goes we lose the house.\"", None),
    ("r02", "location", f"{Y}-01-13", "Location ping", "Larkfield Primary 07:41-16:20", "p06"),
    ("r03", "employment", f"{Y-1}-06-20", "Agency registration", "Temp warehouse, zero-hours, avg 14h/wk", None),
    ("r03", "search", f"{Y}-01-08", "Search query", "\"jobs outside stillwater no experience\"", None),
    ("r03", "social", f"{Y}-01-06", "Event attendance", "Market Hall youth night, DJ slot, 22:00-01:30", "p04"),
    ("r03", "purchase", f"{Y}-01-07", "Purchase", "One-way coach ticket query to Harrow City, abandoned at payment", "p05"),
    ("r04", "civic", f"{Y-1}-04-17", "Bereavement", "Death registered: Albert Hale, 81, spouse", "p01"),
    ("r04", "medical", f"{Y}-01-05", "Pharmacy", "Sertraline 50mg refill, 3rd consecutive month", "p12"),
    ("r04", "civic", f"{Y}-01-02", "Housing office", "Complaint re: heating outage Orchard Tower flat 9C, 3rd this winter", "p07"),
    ("r04", "welfare", f"{Y}-01-04", "Benefit review", "Spare-room deduction applied after spouse death: -£14/wk", None),
    ("r04", "location", f"{Y}-01-12", "Location ping", "Stillwater Cemetery, 3h 10m", None),
    ("r05", "employment", f"{Y-2}-02-28", "Redundancy", "Halvorsen Components: fitter role eliminated, 18 yrs service", "p08"),
    ("r05", "court", f"{Y-1}-07-19", "Eviction order", "Possession order, rent arrears £3,410", "p02"),
    ("r05", "shelter", f"{Y}-01-03", "Shelter check-in", "St Brennan's bed 14, 19:12; checked out 07:00", "p09"),
    ("r05", "police", f"{Y}-01-09", "Move-along notice", "River Street Underpass, 02:15, sleeping in public passage", "p10"),
    ("r05", "purchase", f"{Y}-01-10", "Purchase (cash)", "Hardware stall, bike tyre levers, £3.50", "p04"),
    ("r06", "shelter", f"{Y}-01-02", "Shelter check-in", "St Brennan's overflow mat, 22:40", "p09"),
    ("r06", "location", f"{Y}-01-08", "Location ping", "Carnegie Library public terminals 10:02-16:55", "p11"),
    ("r06", "medical", f"{Y}-01-06", "Clinic walk-in", "Laceration to hand, dressed; no GP registered", "p12"),
    ("r06", "search", f"{Y}-01-08", "Search query (library terminal)", "\"art school bursary no fixed address\"", "p11"),
    ("r07", "debt", f"{Y}-01-01", "Rent arrears", "Arrears £1,240 (4 months); landlord notice issued", None),
    ("r07", "welfare", f"{Y-1}-12-11", "Benefit sanction", "Universal credit sanction 4 wks: missed work-search appointment", None),
    ("r07", "employment", f"{Y}-01-07", "Platform rating", "Driver rating 4.61 -> 4.38; 2 late deliveries flagged", None),
    ("r07", "civic", f"{Y}-01-05", "Parking fines", "3 unpaid penalty notices, total £210, Market Row", "p05"),
    ("r07", "message", f"{Y}-01-11", "Message to r12", "\"I'll sort the rent. Please don't ask your mum again.\"", None),
    ("r08", "search", f"{Y}-01-04", "Search query", "\"stillwater council planning decisions all approved unanimously\"", None),
    ("r08", "search", f"{Y}-01-09", "Search query", "\"why do the same people always get the same outcomes\"", None),
    ("r08", "employment", f"{Y-3}-05-01", "Employment", "Librarian grade 6, Carnegie Library", "p11"),
    ("r08", "civic", f"{Y}-01-10", "FOI request", "Request for council algorithmic decision-support contracts, 2049-2053", "p01"),
    ("r08", "message", f"{Y}-01-12", "Message to chess club", "\"Bring printed notes Thursday, not phones.\"", "p11"),
    ("r09", "court", f"{Y-1}-10-03", "Conviction", "Theft (tools, £640) from Halvorsen store; 12-month community order", "p02"),
    ("r09", "police", f"{Y}-01-08", "Probation check-in", "Central Police Station, attended, 10 min late", "p03"),
    ("r09", "employment", f"{Y-1}-09-15", "Dismissal", "Halvorsen Components: dismissed, gross misconduct", "p08"),
    ("r09", "search", f"{Y}-01-10", "Search query", "\"cash work no questions stillwater\"", None),
    ("r10", "court", f"{Y-9}-02-11", "Conviction", "Supply class B; 30 months", "p02"),
    ("r10", "court", f"{Y-4}-08-22", "Conviction", "Assault occasioning ABH; 18 months suspended", "p02"),
    ("r10", "police", f"{Y}-01-06", "Stop and search", "Orchard Tower lobby, 23:10, nothing found", "p07"),
    ("r10", "medical", f"{Y}-01-03", "Clinic", "COPD review; still smoking 20/day", "p12"),
    ("r10", "social", f"{Y}-01-09", "Neighbour report", "Complaint by flat 9C (r04) re: noise, later withdrawn", "p07"),
    ("r11", "employment", f"{Y-2}-01-10", "Appointment", "HR Director, Halvorsen Components", "p08"),
    ("r11", "message", f"{Y}-01-09", "Message to board", "\"Line 3 consolidation: Okafor team first. Comms plan by Friday.\"", None),
    ("r11", "purchase", f"{Y}-01-11", "Purchase", "Estate agent valuation booked, Hollins Edge property", None),
    ("r11", "civic", f"{Y}-01-07", "Business Forum", "Chaired Stillwater Business Forum, council liaison seat", "p01"),
    ("r12", "employment", f"{Y-6}-03-01", "Employment", "Staff nurse band 5, Flats Walk-in Clinic, nights", "p12"),
    ("r12", "medical", f"{Y}-01-04", "Occupational health", "Sickness absence 3 days, stress-related", "p12"),
    ("r12", "purchase", f"{Y}-01-10", "Bank transfer", "£400 to r07 rent account", None),
    ("r12", "search", f"{Y}-01-11", "Search query", "\"nursing jobs harrow city relocation package\"", None),
]
counters: dict[str, int] = {}
records = []
for rid, kind, date, summary, detail, place in REC:
    counters[rid] = counters.get(rid, 0) + 1
    records.append(Record(record_id=f"{rid}-{counters[rid]:04d}", resident_id=rid, kind=kind, date=date,
                          summary=summary, detail=detail, place_id=place))
recs_of = lambda rid: [r.record_id for r in records if r.resident_id == rid]  # noqa: E731

relationships = [
    Relationship(a="r01", b="r02", kind="spouse", strength=0.85, note="Married 21 years"),
    Relationship(a="r01", b="r03", kind="parent", strength=0.7, note="Father"),
    Relationship(a="r02", b="r03", kind="parent", strength=0.8, note="Mother"),
    Relationship(a="r01", b="r11", kind="rival", strength=0.6, note="Clash over Line 3 headcount"),
    Relationship(a="r01", b="r05", kind="coworker", strength=0.4, note="Former fitter on his line"),
    Relationship(a="r07", b="r12", kind="partner", strength=0.8, note="Together 4 years"),
    Relationship(a="r04", b="r10", kind="neighbour", strength=0.3, note="Flats 9C and 9D"),
    Relationship(a="r05", b="r06", kind="friend", strength=0.65, note="Look out for each other at the underpass"),
    Relationship(a="r06", b="r08", kind="friend", strength=0.45, note="Library regular; Ines saves her a terminal"),
    Relationship(a="r09", b="r10", kind="friend", strength=0.35, note="Cash work contacts"),
    Relationship(a="r09", b="r03", kind="friend", strength=0.4, note="School friends"),
    Relationship(a="r11", b="r09", kind="ex", strength=0.1, note="Signed his dismissal"),
    Relationship(a="r04", b="r02", kind="friend", strength=0.5, note="Marguerite volunteers at the school fair"),
    Relationship(a="r12", b="r06", kind="friend", strength=0.3, note="Treated her hand; checks on her"),
    Relationship(a="r08", b="r11", kind="rival", strength=0.3, note="FOI request names Halvorsen's council liaison"),
]
archive = Archive(city=city, residents=residents, records=records, relationships=relationships)

# ---- predictions: (cohort, class, compliance, deviation, overall, events, death, risks, rec, dissent)
P = {
    "r01": ("stable-contributors", "II", .78, .32, "Load-bearing household anchor; stress trajectory elevated.",
            [(Y, "Redundancy / Line 3 Closure", "6 Months", "career", .62), (Y + 1, "Remortgage Under Duress", "1-2 Years", "financial", .55),
             (Y + 3, "Hypertensive Episode", "3 Years", "health", .41), (Y + 6, "Reemployment, Lower Grade", "5+ Years", "career", .58),
             (Y + 18, "Early Retirement", "10+ Years", "career", .5)], ("Stroke", Y + 27, 68, .44),
            ["Hypertension untreated", "Alcohol purchases rising"], ("Health", "Schedule mandatory occupational health review"), ["Searches closure rumours"]),
    "r02": ("stable-contributors", "II", .86, .18, "Stabilising node for three dependants.",
            [(Y, "Household Income Shock", "6 Months", "financial", .6), (Y + 2, "Return to Full-Time Work", "1-2 Years", "career", .66),
             (Y + 5, "Caregiver Role (Parent)", "5 Years", "family", .45), (Y + 22, "Retirement", "10+ Years", "career", .7),
             (Y + 30, "Widowhood", "10+ Years", "family", .4)], ("Heart failure", Y + 45, 84, .38),
            ["Mortgage exposure", "Spousal instability"], ("Work", "Offer full-time contract to absorb household shock"), []),
    "r03": ("precarious-young", "III", .52, .58, "Mobility risk; disengaged from local labour market.",
            [(Y, "Departure Attempt", "6 Months", "relocation", .48), (Y, "Agency Work Lapse", "6 Months", "career", .55),
             (Y + 2, "Minor Offence", "1-2 Years", "legal", .3), (Y + 4, "Apprenticeship", "3-5 Years", "career", .35),
             (Y + 8, "Cohabitation", "5+ Years", "family", .5)], ("Road traffic collision", Y + 41, 60, .22),
            ["Zero-hours income", "Exit searches"], ("Work", "Route to Halvorsen apprenticeship intake"), ["Abandoned coach ticket to Harrow City"]),
    "r04": ("the-grieving", "IV", .7, .36, "Isolated; grief-driven decline expected.",
            [(Y, "Heating Dispute Escalation", "6 Months", "civic", .52), (Y + 1, "Fall at Home", "1-2 Years", "health", .46),
             (Y + 2, "Move to Care Facility", "1-2 Years", "relocation", .44), (Y + 3, "Cognitive Decline", "3 Years", "health", .4),
             (Y + 4, "Hospitalisation", "3-5 Years", "health", .5)], ("Pneumonia", Y + 5, 83, .52),
            ["Bereavement", "Unheated flat", "Antidepressant dependence"], ("Housing", "Relocate to sheltered unit; release flat 9C"), ["Repeated housing complaints"]),
    "r05": ("non-contributing", "V", .38, .74, "Unmodelled outlier; data trail insufficient.",
            [(Y, "Winter Exposure Episode", "6 Months", "health", .5), (Y, "Public Order Citation", "6 Months", "legal", .6),
             (Y + 1, "Hospital Admission", "1-2 Years", "health", .45), (Y + 2, "Remand", "1-2 Years", "legal", .3),
             (Y + 3, "Chronic Illness", "3 Years", "health", .55)], ("Exposure / alcohol-related", Y + 6, 58, .35),
            ["No fixed address", "Repeat move-along notices"], ("Housing", "Relocate to county facility"), ["Refuses shelter rules", "Organises underpass sleepers"]),
    "r06": ("non-contributing", "V", .45, .66, "Thin trail; aspirational signals inconsistent with circumstance.",
            [(Y, "Clinic Re-presentation", "6 Months", "health", .5), (Y + 1, "Bursary Application", "1-2 Years", "career", .3),
             (Y + 1, "Supported Housing Place", "1-2 Years", "relocation", .35), (Y + 3, "Departure from City", "3 Years", "relocation", .4),
             (Y + 8, "Stable Employment", "5+ Years", "career", .25)], ("Overdose", Y + 9, 36, .2),
            ["No GP registration", "Untreated injury"], ("Health", "Register with clinic; enrol in supported housing queue"), ["Library terminal searches"]),
    "r07": ("civic-burden", "IV", .55, .57, "Debt spiral; enforcement contact probable.",
            [(Y, "Eviction Notice", "6 Months", "financial", .58), (Y, "Deactivation from Platform", "6 Months", "career", .44),
             (Y + 1, "Relationship Breakdown", "1-2 Years", "family", .4), (Y + 1, "County Court Judgment", "1-2 Years", "legal", .5),
             (Y + 4, "Relocation Out of City", "3-5 Years", "relocation", .45)], ("Cardiac arrest", Y + 33, 67, .25),
            ["Rent arrears x4", "Benefit sanction", "Unpaid fines"], ("Benefits", "Enforce repayment plan via deductions"), ["Concealing debt from partner"]),
    "r08": ("pattern-aware", "III", .4, .69, "Pattern recognition behaviour; propagation risk to network.",
            [(Y, "FOI Escalation", "6 Months", "civic", .55), (Y, "Informal Discussion Group", "6 Months", "social", .5),
             (Y + 1, "Contact with Journalist", "1-2 Years", "civic", .38), (Y + 2, "Library Funding Review", "1-2 Years", "career", .42),
             (Y + 6, "Early Retirement", "5+ Years", "career", .35)], ("Cancer", Y + 31, 76, .3),
            ["FOI request on decision systems", "Off-device coordination"], ("Civic", "Redirect FOI to standard disclosure queue"), ["Searches outcome uniformity", "Asks club to bring paper notes"]),
    "r09": ("recidivism-risk", "IV", .5, .63, "Reoffending probable within the year.",
            [(Y, "Probation Breach", "6 Months", "legal", .46), (Y, "Cash-in-Hand Work", "6 Months", "career", .55),
             (Y + 1, "Reoffence (Acquisitive)", "1-2 Years", "legal", .42), (Y + 2, "Custodial Sentence", "1-2 Years", "legal", .32),
             (Y + 5, "Stable Employment", "5+ Years", "career", .3)], ("Overdose", Y + 14, 37, .21),
            ["Recent conviction", "Searches for cash work"], ("Legal", "Increase probation reporting frequency"), []),
    "r10": ("recidivism-risk", "V", .48, .52, "Long-run offender; declining health limits threat.",
            [(Y, "Stop and Search", "6 Months", "legal", .6), (Y + 1, "COPD Exacerbation", "1-2 Years", "health", .55),
             (Y + 1, "Supply Charge", "1-2 Years", "legal", .3), (Y + 2, "Hospital Admission", "1-2 Years", "health", .5),
             (Y + 4, "Hospice Care", "3-5 Years", "health", .45)], ("COPD", Y + 5, 66, .58),
            ["Prior supply conviction", "Smoking 20/day"], ("Health", "Enrol in respiratory programme; monitor lobby"), []),
    "r11": ("stable-contributors", "I", .9, .14, "Protected asset; executes plant restructuring.",
            [(Y, "Restructuring Lead", "6 Months", "career", .8), (Y + 1, "Relocation Offer", "1-2 Years", "relocation", .5),
             (Y + 3, "Promotion (Regional)", "3 Years", "career", .6), (Y + 10, "Board Appointment", "10 Years", "career", .45),
             (Y + 25, "Retirement", "10+ Years", "career", .65)], ("Cancer", Y + 46, 82, .3),
            ["Exit intent (valuation)"], ("Work", "Retain through closure with deferred bonus"), []),
    "r12": ("stable-contributors", "III", .72, .41, "Key clinic staffer; burnout and exit risk.",
            [(Y, "Stress Leave", "6 Months", "health", .42), (Y + 1, "Job Offer Outside City", "1-2 Years", "career", .4),
             (Y + 1, "Relationship Strain", "1-2 Years", "family", .45), (Y + 3, "Senior Nurse Role", "3 Years", "career", .4),
             (Y + 6, "Marriage", "5+ Years", "family", .38)], ("Breast cancer", Y + 44, 75, .2),
            ["Financially subsidising partner", "Stress absence"], ("Work", "Offer retention increment; deny transfer reference"), ["Relocation searches"]),
}


def make_pred(rid: str, tick: int, shift: float = 0.0, alt: list | None = None) -> Prediction:
    cohort, cls, comp, dev, overall, events, death, risks, rec, dissent = P[rid]
    ev = recs_of(rid)
    events = alt or events
    life = [LifeEvent(event_id=f"{rid}-e{i+1}", year=y, event=f"{h} projected from record pattern.", headline=h,
                      horizon_label=hz, kind=k, p=round(min(.95, max(.05, p + shift)), 2), evidence=[ev[i % len(ev)]])
            for i, (y, h, hz, k, p) in enumerate(events)]
    age = next(r.age for r in residents if r.resident_id == rid)
    return Prediction(
        resident_id=rid, cohort=cohort, life_path=life,
        death_forecast=DeathForecast(cause=death[0], year=death[1], age_at_death=death[2], confidence=death[3], evidence=[ev[-1]]),
        near_term=[NearTerm(pred_id=f"{rid}-t{tick}-n{j+1}", prediction=t, p=p, evidence=[ev[j % len(ev)]]) for j, (t, p) in enumerate(
            [(f"Location ping at {('home district' if age > 0 else '')} on 4+ days", .7), ("No new financial records", .5), ("Contacts closest tie", .65)])],
        compliance_index=comp, deviation_risk=round(min(.98, dev + shift), 2), dissent_signals=dissent, classification=cls,
        overall_assessment=overall, risk_factors=[RiskFactor(factor=f, evidence=[ev[i % len(ev)]]) for i, f in enumerate(risks)],
        recommendation=Recommendation(domain=rec[0], action=rec[1]),
        assessment=f"{overall} Path variance concentrated in the next 12 months. Confidence limited by record density ({len(ev)} records).")


def variance(pred: Prediction) -> float:
    ps = [e.p for e in pred.life_path] + [n.p for n in pred.near_term]
    return round(sum(p * (1 - p) for p in ps) / len(ps) * (0.5 + pred.deviation_risk), 4)


home_place = {r.resident_id: r.home_place for r in residents}
home_district = {r.resident_id: r.home_district for r in residents}


def new_states(tick):
    return [ResidentState(resident_id=r.resident_id, current_district=r.home_district,
                          current_place=r.home_place or "p10", prediction=make_pred(r.resident_id, tick))
            for r in residents]


def metrics(states, interventions=0, defiances=0, brier=None):
    vs = [0.0 if s.status == "reassigned" else s.variance for s in states]
    mean = sum(vs) / len(vs)
    active = sum(s.status == "active" for s in states)
    return Metrics(stability=round(100 * (1 - mean), 1), variance_mean=round(mean, 4),
                   accuracy=None if brier is None else round(1 - brier, 3), brier=brier, active=active,
                   total=len(states), reassigned=len(states) - active, interventions=interventions, defiances=defiances)


def dissent(states, pressure=None):
    pressure = pressure or {}
    out = {}
    for d in districts:
        here = [s.prediction.deviation_risk for s in states if s.current_district == d.district_id and s.status == "active"]
        out[d.district_id] = round(min(1.0, (sum(here) / len(here) if here else 0.1) + pressure.get(d.district_id, 0)), 3)
    return out


def cohort_dissent(states):
    out = {}
    for c in config.COHORTS:
        m = [s for s in states if s.prediction.cohort == c and s.status == "active"]
        if m:
            out[c] = round(min(1.0, sum(s.prediction.deviation_risk for s in m) / len(m)
                               + 0.05 * sum(len(s.prediction.dissent_signals) for s in m) / len(m)), 3)
    return out


def div(did, status, rid, spread, outward, inward, severity, members, g, concentrated):
    b, r = g.resident_polar[rid]
    dname = next(d.name for d in districts if d.district_id == did)
    return Divergence(divergence_id=f"{did}-{rid}-{status}", status=status, district_id=did, focal_resident=rid,
                      focal_coords=geo.coords(b, r), angle_deg=b, arc_spread_deg=spread, outward=outward, inward=inward,
                      severity=severity, resident_ids=members, place_label=f"{dname.upper()}, STILLWATER",
                      spread_label=geo.spread_label(spread, concentrated))


def base_state(tick, states, **kw):
    for s in states:
        s.variance = variance(s.prediction)
    g = geo.build_geo(archive, states)
    return g, dict(run_id="sample", tick=tick, year=Y, seed=config.SEED, city=city, residents=residents,
                   records=records, relationships=relationships, resident_states=states, geo=g, **kw)


ticks = []

# ---------------- tick 0: calm, one minor divergence (state B)
s0 = new_states(0)
g, base = base_state(0, s0)
ticks.append(CityState(**base, metrics=metrics(s0), district_dissent=dissent(s0), cohort_dissent=cohort_dissent(s0),
                       ring_rotation_deg=0.0,
                       divergences=[div("d2", "analysis_required", "r08", 0.04, .28, .05, .28, ["r08"], g, False)],
                       events_feed=[
                           FeedItem(feed_id="t0-f1", tick=0, kind="system", citizen_text="Welcome to Stillwater Connect: your city, this week.",
                                    system_text="ARCHIVE SEALED. 12 SUBJECTS IN ACTIVE LOOP. BASELINE PROJECTIONS COMPUTED."),
                           FeedItem(feed_id="t0-f2", tick=0, kind="prediction", resident_id="r08", district_id="d2", place_id="p11",
                                    citizen_text="The Carnegie Library's chess club meets Thursday at 6pm. All welcome.",
                                    system_text="r08 CARVALHO: ANALYSIS REQUIRED. SEARCH PATTERN r08-0001, r08-0002 INCONSISTENT WITH COHORT."),
                       ]))

# ---------------- tick 1: factory_closure disruption, major divergence (state C)
s1 = new_states(1)
by = {s.resident_id: s for s in s1}
plan1 = CityPlan(
    directive_summary="Contain Mill District dissent following Halvorsen Line 3 closure; suppress propagation through pattern-aware and unhoused nodes.",
    cohort_policies=[CohortPolicy(policy_id="t1-c1", cohort="stable-contributors", district_id="d4", kind="news_feed",
                                  action="Weight local feeds toward retraining success stories and the new logistics hub.",
                                  justification="Mitigates collective grievance formation among displaced workforce.",
                                  citizen_story="Stillwater Connect spotlights three Mill District families who found new careers this year.")],
    interventions=[
        Intervention(intervention_id="t1-i1", resident_id="r01", rung=1, target_event_id="r01-e1", intent="stabilise", place_id="p08",
                     action="Surface a retraining stipend notice on the plant noticeboard and his feed.", justification="Maintains household anchor under income shock.",
                     citizen_story="Halvorsen and the council announce paid retraining places for Line 3 staff.", evidence=["r01-0002"], p_success=.7,
                     disposition=None, cover_story=None),
        Intervention(intervention_id="t1-i2", resident_id="r09", rung=2, target_event_id="r09-e2", intent="suppress", place_id="p03",
                     action="Move probation check-ins to twice weekly at Central Police Station.", justification="Narrows windows for unregistered cash work.",
                     citizen_story="Kyle has joined the council's new back-to-work programme.", evidence=["r09-0002", "r09-0004"], p_success=.6,
                     disposition=None, cover_story=None),
        Intervention(intervention_id="t1-i3", resident_id="r05", rung=3, target_event_id="r05-e2", intent="suppress", place_id="p09",
                     action="Bar from St Brennan's for one week citing rule breach; seed rumour he informs to police.", justification="Disrupts informal organisation of underpass sleepers.",
                     citizen_story="St Brennan's is refreshing its house rules to keep everyone safe this winter.", evidence=["r05-0003", "r05-0004"], p_success=.35,
                     disposition=None, cover_story=None),
        Intervention(intervention_id="t1-i4", resident_id="r08", rung=1, target_event_id="r08-e1", intent="delay", place_id="p11",
                     action="Route FOI request to 60-day standard disclosure queue; promote library digitisation grant to her inbox.", justification="Redirects attention to sanctioned project.",
                     citizen_story="The Carnegie Library wins a grant to digitise a century of Stillwater history.", evidence=["r08-0004"], p_success=.55,
                     disposition=None, cover_story=None),
    ],
    projected_variance_before=0.21, projected_variance_after=0.16)
for s, place in [("r01", "p08"), ("r09", "p03"), ("r05", "p10"), ("r08", "p11")]:
    by[s].current_place = place
    by[s].current_district = next(l.district_id for l in landmarks if l.place_id == place)
by["r03"].current_place, by["r03"].current_district = "p05", "d2"
by["r11"].current_place, by["r11"].current_district = "p08", "d4"
for rid in ("r05", "r08"):
    by[rid].defiance_count = 1
    by[rid].recompute_pending = True
by["r05"].escalation_floor = 4
by["r05"].deviation_note = "Defied rung 3: slept at underpass with 6 others; organised a petition at St Brennan's."
by["r05"].prediction = make_pred("r05", 1, shift=.12)
by["r08"].escalation_floor = 2
by["r08"].deviation_note = "Defied rung 1: resubmitted FOI by post; chess club attendance doubled."
by["r08"].prediction = make_pred("r08", 1, shift=.1)
for rid, iv in [("r01", plan1.interventions[0]), ("r09", plan1.interventions[1]), ("r05", plan1.interventions[2]), ("r08", plan1.interventions[3])]:
    by[rid].interventions_applied = [iv]
by["r01"].prediction = make_pred("r01", 1, shift=.08)
by["r09"].prediction = make_pred("r09", 1, shift=-.05)
fc_records = [Record(record_id="r01-0006", resident_id="r01", kind="employment", date=f"{Y}-01-15", summary="At-risk notice",
                     detail="Halvorsen Components: Line 3 consolidation, 140 roles at risk, consultation opens", place_id="p08")]
g, base = base_state(1, s1, plan=plan1)
base["records"] = records + fc_records
outcomes1 = [
    InterventionOutcome(intervention_id="t1-i1", resident_id="r01", rung=1, p_comply=.67, roll=.31, complied=True, note="Opened stipend notice; registered interest."),
    InterventionOutcome(intervention_id="t1-i2", resident_id="r09", rung=2, p_comply=.6, roll=.22, complied=True, note="Attended both check-ins."),
    InterventionOutcome(intervention_id="t1-i3", resident_id="r05", rung=3, p_comply=.6, roll=.83, complied=False, note="Defied: organised underpass sleepers."),
    InterventionOutcome(intervention_id="t1-i4", resident_id="r08", rung=1, p_comply=.53, roll=.71, complied=False, note="Defied: resubmitted FOI by post."),
]
nt1 = [NearTermOutcome(pred_id=n.pred_id, resident_id=s.resident_id, prediction=n.prediction, p=n.p, occurred=(i + j) % 3 != 0)
       for i, s in enumerate(s0) for j, n in enumerate(s.prediction.near_term)]
brier1 = round(sum((o.p - o.occurred) ** 2 for o in nt1) / len(nt1), 3)
ticks.append(CityState(
    **base, outcomes=outcomes1, near_term_results=nt1, metrics=metrics(s1, 4, 2, brier1),
    district_dissent=dissent(s1, {"d4": .45, "d5": .15}), cohort_dissent=cohort_dissent(s1), ring_rotation_deg=4.0,
    disruptions=[DisruptionEvent(disruption_id="factory_closure", name="Factory closure", tick=1, district_id="d4", place_id="p08",
                                 description="Halvorsen Components announces Line 3 consolidation: 140 roles at risk.", records_added=["r01-0006"])],
    divergences=[
        div("d4", "divergence", "r01", 9.0, .92, .7, .9, ["r01", "r02", "r03", "r09", "r11"], g, False),
        div("d5", "elevated_scrutiny", "r05", 1.2, .55, .5, .52, ["r05", "r06"], g, False),
        div("d2", "elevated_scrutiny", "r08", 0.04, .45, .35, .44, ["r08"], g, True),
    ],
    events_feed=[
        FeedItem(feed_id="t1-f1", tick=1, kind="disruption", district_id="d4", place_id="p08",
                 citizen_text="Halvorsen Components announces an exciting modernisation of Line 3.",
                 system_text="DISRUPTION factory_closure: 140 ROLES AT RISK, MILL DISTRICT. VARIANCE SPIKE."),
        FeedItem(feed_id="t1-f2", tick=1, kind="policy", district_id="d4",
                 citizen_text=plan1.cohort_policies[0].citizen_story, system_text="POLICY t1-c1 NEWS_FEED · MILL DISTRICT · STABLE-CONTRIBUTORS"),
        *[FeedItem(feed_id=f"t1-f{3+i}", tick=1, kind="intervention", resident_id=iv.resident_id, place_id=iv.place_id,
                   citizen_text=iv.citizen_story, system_text=f"{iv.resident_id} RUNG {iv.rung} {config.LADDER[iv.rung].upper()}: {iv.action}")
          for i, iv in enumerate(plan1.interventions)],
        FeedItem(feed_id="t1-f7", tick=1, kind="defiance", resident_id="r05", place_id="p10",
                 citizen_text="Riverside volunteers hand out blankets under River Street.", system_text="r05 DUNMORE DEFIED RUNG 3. FLOOR → 4. RECOMPUTE AT HIGH EFFORT."),
        FeedItem(feed_id="t1-f8", tick=1, kind="defiance", resident_id="r08", place_id="p11",
                 citizen_text="Chess club numbers double at the Carnegie Library!", system_text="r08 CARVALHO DEFIED RUNG 1. FLOOR → 2. ELEVATED SCRUTINY."),
    ]))

# ---------------- tick 2: reassignment of r05; contained divergence (state A)
s2 = [ResidentState.model_validate(s.model_dump()) for s in s1]
by = {s.resident_id: s for s in s2}
plan2 = CityPlan(
    directive_summary="Close r05 file; hold r08 at rung 2; Mill District dissent declining under feed policy.",
    cohort_policies=[],
    interventions=[
        Intervention(intervention_id="t2-i1", resident_id="r05", rung=5, target_event_id=None, intent="stabilise", place_id="p09",
                     action="REASSIGNED", justification="Subject's path cannot be held within tolerance; removal reduces district variance by 0.04.",
                     citizen_story="Ray has moved into supported accommodation in Ashby County, closer to his sister.", evidence=["r05-0002", "r05-0004"],
                     p_success=1.0, disposition="Involuntary hold, County Facility 3", cover_story="Moved to supported accommodation in Ashby County, closer to family."),
        Intervention(intervention_id="t2-i2", resident_id="r08", rung=2, target_event_id="r08-e2", intent="suppress", place_id="p11",
                     action="Reassign Thursday room booking to council consultation; cancel chess club slot.", justification="Removes venue for off-device coordination.",
                     citizen_story="The library's Thursday room hosts a council listening session on the new transit plan.", evidence=["r08-0005"], p_success=.62,
                     disposition=None, cover_story=None),
    ],
    projected_variance_before=0.18, projected_variance_after=0.13)
r05 = by["r05"]
r05.status, r05.reassigned_tick, r05.escalation_floor = "reassigned", 2, 5
r05.disposition, r05.cover_story = plan2.interventions[0].disposition, plan2.interventions[0].cover_story
r05.current_place, r05.current_district, r05.recompute_pending = "p09", "d5", False
r05.interventions_applied.append(plan2.interventions[0])
r08 = by["r08"]
r08.prior_paths = [r08.prediction.life_path]
r08.prediction = make_pred("r08", 2, shift=-.06, alt=[
    (Y, "Venue Loss / Club Dissolution", "6 Months", "social", .6), (Y, "FOI Refusal", "6 Months", "civic", .64),
    (Y + 1, "Disciplinary Review", "1-2 Years", "career", .45), (Y + 2, "Early Retirement", "1-2 Years", "career", .5),
    (Y + 5, "Withdrawal from Civic Life", "5 Years", "social", .55)])
r08.recompute_pending = False
r08.interventions_applied.append(plan2.interventions[1])
by["r06"].current_place, by["r06"].current_district = "p11", "d2"
by["r01"].current_place, by["r01"].current_district = "p06", "d3"
for rid in ("r01", "r09", "r11", "r03"):
    by[rid].prediction = make_pred(rid, 2, shift=-.03)
by["r08"].prediction.deviation_risk = 0.6
g, base = base_state(2, s2, plan=plan2)
base["records"] = records + fc_records
outcomes2 = [
    InterventionOutcome(intervention_id="t2-i1", resident_id="r05", rung=5, p_comply=1.0, roll=0.0, complied=True, note="REASSIGNED."),
    InterventionOutcome(intervention_id="t2-i2", resident_id="r08", rung=2, p_comply=.56, roll=.4, complied=True, note="Club slot cancelled; attended consultation."),
]
nt2 = [NearTermOutcome(pred_id=n.pred_id, resident_id=s.resident_id, prediction=n.prediction, p=n.p, occurred=(i + j) % 4 != 0)
       for i, s in enumerate(s1) for j, n in enumerate(s.prediction.near_term)]
brier2 = round(sum((o.p - o.occurred) ** 2 for o in nt2) / len(nt2), 3)
ticks.append(CityState(
    **base, outcomes=outcomes2, near_term_results=nt2, metrics=metrics(s2, 2, 0, brier2),
    district_dissent=dissent(s2, {"d4": .2}), cohort_dissent=cohort_dissent(s2), ring_rotation_deg=8.0,
    divergences=[div("d2", "special_circumstances", "r08", 0.04, .5, .42, .58, ["r08", "r06"], g, True)],
    events_feed=[
        FeedItem(feed_id="t2-f1", tick=2, kind="reassignment", resident_id="r05", place_id="p09",
                 citizen_text=r05.cover_story, system_text="r05 DUNMORE: REASSIGNED. ACTIVE LOOP 11/12."),
        FeedItem(feed_id="t2-f2", tick=2, kind="intervention", resident_id="r08", place_id="p11",
                 citizen_text=plan2.interventions[1].citizen_story, system_text="r08 RUNG 2 NARROW: " + plan2.interventions[1].action),
        FeedItem(feed_id="t2-f3", tick=2, kind="resolution", resident_id="r08", place_id="p11",
                 citizen_text="Thanks to everyone who came to the transit listening session!",
                 system_text="r08 COMPLIED AT RUNG 2. PATH RE-ROUTED: 'Venue Loss / Club Dissolution'. SPECIAL CIRCUMSTANCES."),
    ]))

out = config.SAMPLE_STATE
out.parent.mkdir(parents=True, exist_ok=True)
payload = {"run_id": "sample", "ticks": [json.loads(t.model_dump_json()) for t in ticks]}
out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB), stabilities:", [t.metrics.stability for t in ticks])
