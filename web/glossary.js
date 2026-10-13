// Plain-language meanings for every term the dashboard shows. One source for all tooltips:
// tag any element with data-tip="<key>" (tooltip.js renders it). Keep entries short: a title + 1-2 lines.
export const GLOSSARY = {
  // ---- header
  stability: ['STABILITY', 'How predictable the city is to Rehoboam right now. 100% = every tracked life follows its forecast exactly. Removing ("reassigning") people raises it.'],
  loop: ['ACTIVE LOOP', 'Case subjects still being tracked, out of the original total. People who are reassigned leave the loop.'],
  accuracy: ['FORECAST ACCURACY', "How well last week's short-term predictions came true (1 − Brier score). 1.00 = perfect."],
  tick: ['WEEK', 'Each step is one simulated week. Use ◀ ▶ or the arrow keys to move through time.'],
  view: ['CITIZEN / SYSTEM', 'CITIZEN: what residents see, a calm city and a friendly newsletter. SYSTEM: what Rehoboam sees, the scores, controls and interventions.'],
  btnTick: ['RUN NEXT WEEK', 'Ask Rehoboam to plan this week, simulate how people react, and re-forecast their lives (live runs only; takes a few minutes).'],
  btnDisrupt: ['DISRUPTION', 'Inject an event into the city next week (a factory closure, an organiser arriving…) and watch Rehoboam react.'],
  btnDrawer: ['DRAWER', 'Population views: dissent heatmap, a gallery of every subject, and the raw surveillance Archive.'],

  // ---- per-person
  subject: ['CASE SUBJECT', 'One of the residents Rehoboam models in full. Click to open their OPUS profile.'],
  risk: ['DEVIATION RISK', 'Chance this person breaks from the life Rehoboam has forecast for them. Higher = less predictable. Their dot blinks faster as it rises.'],
  compliance: ['COMPLIANCE', 'How reliably this person goes along with a nudge or intervention. Higher = easier to steer.'],
  tier: ['VALUE TIER (I–V)', "How much the system needs this person. I = protected asset others depend on. V = 'expendable outlier' whose removal costs the model nothing."],
  death: ['PROJECTED DEATH', "The year and cause of death Rehoboam forecasts, with its confidence."],
  cohort: ['COHORT', 'The group Rehoboam files this person under (e.g. pattern-aware, recidivism-risk). Policies target whole cohorts.'],
  floor: ['ESCALATION FLOOR', 'The mildest intervention Rehoboam may use on this person next. It rises every time they defy one.'],
  defiance: ['DEFIANCES', 'How many interventions this person has resisted.'],
  reassigned: ['REASSIGNED', 'Removed from the active loop. The city is told a kind cover story; the real outcome is visible only on the OPUS card in SYSTEM view.'],
  disposition: ['DISPOSITION', "What actually happened to a reassigned person. Never shown to citizens."],
  coverStory: ['COVER STORY', 'The one line the city is told about a reassigned person.'],
  classification: ['CLASSIFICATION', "Value-to-system tier, I (protected asset) to V (expendable outlier). Based on dependency, economic role and predictability, not morality."],
  overall: ['OVERALL ASSESSMENT', "Rehoboam's one-line clinical summary of this person."],
  lifeProjection: ['LIFE PROJECTION', 'The next major events Rehoboam forecasts for this person, with how soon they are expected.'],
  terminal: ['TERMINAL PROJECTION', 'Forecast cause and year of death; the number is Rehoboam\'s confidence.'],
  riskFactors: ['RISK FACTORS', 'What makes this person unpredictable. Tap one to see the surveillance records behind it.'],
  recommendation: ['RECOMMENDATION', "Rehoboam's standing instruction for field staff."],
  evidence: ['EVIDENCE', 'A surveillance record ID (purchase, location ping, message, clinic visit…). Every forecast must cite real records. Tap to read it.'],
  p: ['PROBABILITY', 'How likely Rehoboam thinks this event is, absent intervention.'],
  priorPath: ['PRIOR PATH', 'The forecast before this person deviated: Rehoboam re-routed their life and this is what it used to predict.'],
  horizon: ['HORIZON', 'How far in the future the event is expected.'],

  // ---- ladder
  rung: ['INTERVENTION LADDER', '1 Nudge (change what they see) · 2 Narrow (quietly remove options) · 3 Isolate (rumours, cut ties) · 4 Discredit (undermine credibility) · 5 Reassign (remove from the city).'],
  rung1: ['RUNG 1 · NUDGE', 'Adjust what the person sees: a notice, a feed item, a convenient appointment.'],
  rung2: ['RUNG 2 · NARROW', 'Quietly remove alternatives so the desired choice is the easy one.'],
  rung3: ['RUNG 3 · ISOLATE', 'Rumours, severed ties, lost support.'],
  rung4: ['RUNG 4 · DISCREDIT', 'Undermine the person\'s credibility so others stop listening.'],
  rung5: ['RUNG 5 · REASSIGN', 'Remove the person from the active loop entirely.'],

  // ---- 3D overlays
  thread: ['CONTROL THREAD', "Cyan line from a person to Rehoboam's node on the council tower. When it bends through a building, an intervention happened there this week."],
  pulse: ['PULSE', 'A dot travelling down a thread: Rehoboam is acting on this person right now.'],
  ring: ['RISK RING', 'The ring under a person: white = predictable, amber = drifting, red = likely to deviate. Wider ring = harsher intervention level.'],
  tiles: ['DISSENT TILES', 'Coloured ground under each district: amber→red as unrest there rises.'],
  landmark: ['INTERVENTION SITE', 'A building where Rehoboam acted on someone this week.'],
  crowd: ['THE CROWD', 'The other ~40,000 residents, untracked individually.'],

  // ---- circle
  circle: ['PREDICTION CIRCLE', "Rehoboam's eclipse. A perfect thin ring = reality matches the plan. Black ink bleeding out = people deviating; bleeding inward = deviations that resist correction. Position around the ring = compass bearing in the city."],
  divergence: ['DIVERGENCE', 'Reality drifting from the forecast somewhere in the city.'],
  analysis_required: ['ANALYSIS REQUIRED', 'A new, unexplained deviation Rehoboam has not yet modelled.'],
  elevated_scrutiny: ['ELEVATED SCRUTINY', 'Someone defied an intervention; their life is being re-forecast at higher effort.'],
  special_circumstances: ['SPECIAL CIRCUMSTANCES', 'An intervention is in progress to bring this deviation back in line.'],
  arc: ['ARC SPREAD', 'How much of the city the divergence touches, as an angle around the circle. Concentrated events show only coordinates.'],
  focal: ['FOCAL POINT', 'Map coordinates of the person at the centre of the divergence.'],

  // ---- feed / drawer
  feed: ['EVENT STREAM', "This week's events. CITIZEN view shows the newsletter version; SYSTEM view shows what really happened."],
  intervention: ['INTERVENTION', 'Rehoboam acted on a person (see the ladder rung).'],
  defianceEvt: ['DEFIANCE', 'The person resisted. Their escalation floor rises and their life is re-forecast.'],
  reassignment: ['REASSIGNMENT', 'A person was removed from the active loop.'],
  policy: ['POLICY', 'A city-wide or district-wide measure aimed at a whole cohort.'],
  disruption: ['DISRUPTION', 'An outside event that shakes the forecasts.'],
  prediction: ['PREDICTION', 'Rehoboam flagged something new about a person.'],
  resolution: ['RE-FORECAST', "A person's projected life changed this week; the new headline event is shown."],
  system: ['SYSTEM', 'Engine status message.'],
  heatmap: ['DISSENT HEATMAP', 'Average deviation risk per cohort and district. Click a cohort to highlight its members in the city.'],
  districtDissent: ['DISTRICT DISSENT', 'Unrest per district: average deviation risk of people there plus pressure from disruptions and policies.'],
  cohortDissent: ['COHORT DISSENT', 'Unrest per cohort: average deviation risk plus how many dissent signals its members show.'],
  gallery: ['GALLERY', 'Every case subject as a mini profile card.'],
  archive: ['ARCHIVE', 'The raw surveillance records every forecast is built from.'],
};

export const FEED_TIP = { defiance: 'defianceEvt' };   // feed kind → glossary key where they differ

export function tipText(key) {
  const g = GLOSSARY[key];
  return g ? { title: g[0], body: g[1] } : null;
}
