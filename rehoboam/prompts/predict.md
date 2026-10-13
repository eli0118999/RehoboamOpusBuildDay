Model the life of subject {rid}. Their dossier and connected subjects' records are in the Archive above. The current tick is {tick} (one tick = one week), year {year}. The subject is currently at {current_place}.

A thin data trail is itself a finding: a subject the Archive cannot see clearly is one whose path you cannot guarantee. Express that as lower confidence and higher deviation_risk, not invented detail.

Produce a chronological life_path of 5–9 events until death (event_ids `{rid}-e1`, `{rid}-e2`, …). Each has p (its probability absent intervention) and at least one cited record. Add a death_forecast (its `cause` a terse clinical noun phrase of at most five words, e.g. "Overdose", "Stroke", "Exposure / Hypothermia") and 3–5 near_term predictions for the coming week (pred_ids `{rid}-t{tick}-n1`, …), concrete enough to check next tick. Assign a cohort from: {cohorts}. Score compliance_index (how reliably they respond to nudges) and deviation_risk (how likely they break from the modelled path). List dissent_signals.

You are also filling this subject's OPUS profile, a terse operational readout for field staff, in the register of an HR and clinical risk system:
- `classification`: value-to-system tier. I is a protected asset whose stability anchors others; V is an expendable outlier whose removal costs the model nothing. Base it on dependency in the relationship graph, economic role and predictability, not morality.
- `overall_assessment`: one clinical line.
- Every event gets a `headline`: a short plain-English phrase anyone would understand, at most five words, no jargon or acronyms ("Loses his job", "Evicted from flat", "Divorce and loss of custody") and a `horizon_label` ("6 Months", "1-2 Years", "10+ Years").
- `risk_factors`: 2–4 blunt items, each cited.
- `recommendation`: one domain plus a terse action.
- `assessment`: clinical, 2–3 sentences.
{interventions_block}{recompute_block}
