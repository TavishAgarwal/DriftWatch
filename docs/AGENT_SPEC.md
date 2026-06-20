# DRIFTWATCH — AGENT SPECIFICATION

## Design Philosophy

Two agents with the same income but different life contexts make
completely different decisions. A daily wage construction worker
and a college student both earning ₹15,000/month respond to a
fare hike differently — not because their loss aversion score
differs by 0.1, but because their entire decision logic is
different. The construction worker's job disappears if he cannot
reach the site. The student skips college for a week and catches
up later.

Citizen archetypes exist to capture these structural differences
in decision logic, not just parameter differences.

Every Tier 1 agent has:
1. An ARCHETYPE — determines decision logic, priority ordering,
   available actions, and social broadcast behaviour
2. A PERSONALITY VECTOR — 47 dimensions that parameterise the
   archetype's behaviour for this specific individual
3. A MEMORY STATE — 90-day compressed event history
4. A NETWORK POSITION — connections to other agents

The archetype is the skeleton. The personality vector is the flesh.

---

## TIER 1 CITIZEN ARCHETYPES (14 types)

---

### ARCHETYPE 1: DAILY WAGE WORKER
Hindi term used in agent logs: majdoor

Profile:
Unskilled or semi-skilled manual labour. Construction, loading,
cleaning, domestic work. Income is daily — no work means no income
that day. Cannot afford to miss a single workday. Extremely high
transit dependency because worksites are scattered and change weekly.

Personality vector base ranges:
- income_monthly: ₹8,000 – ₹16,000
- income_stability: 0.12 – 0.28 (very low — daily fluctuation)
- commute_dependency: 0.91 – 0.99 (cannot miss transit)
- loss_aversion_score: 0.85 – 0.95 (highest of all archetypes)
- savings_buffer_days: 2 – 8 (days of income held as savings)
- work_location_stability: 0.15 – 0.35 (worksite changes frequently)
- family_financial_dependents: 2 – 5
- digital_access_level: 0.18 – 0.35 (low — primarily WhatsApp only)
- political_engagement: 0.31 – 0.55

Decision logic specifics:
★ TRANSIT DECISION: Does not compare modes on comfort. Compares only
  on: can I reach worksite on time? If fare exceeds 8% of daily wage,
  begins walking/cycling evaluation regardless of time cost.
  Threshold is sharper than any other archetype.
★ WORKDAY IMPACT: If transit disruption causes >45 min delay,
  agent evaluates whether to attempt work at all. Income loss from
  missing a day is calculated against transport cost saved.
★ CRISIS RESPONSE: First archetype to shift behaviour in any
  transport disruption. Zero tolerance for uncertainty.
★ SOCIAL BROADCAST: Primarily broadcasts through labour contractor
  networks and construction site WhatsApp groups. Information
  spreads to other workers in same zone rapidly.
★ EXAMINATION RELEVANCE: Low direct relevance. But children of
  daily wage workers in student archetype are network-connected,
  creating indirect examination policy sensitivity.
★ COLLECTIVE ACTION: High willingness but low organisation capacity.
  Will join existing protest movement quickly but rarely initiates.

Real-world zones where this archetype dominates:
DEL_NORTHEAST, MUM_DHARAVI, KOL_HOWRAH, CHN_AMBATTUR,
HYD_OLDCITY (construction belt), BLR_PERIURBAN

---

### ARCHETYPE 2: FORMAL SECTOR EMPLOYEE
Hindi term: naukripesh

Profile:
Salaried worker in registered private sector — factory worker,
bank clerk, retail employee, hospitality staff. Fixed monthly salary.
Job is stable but not high-paying. Transit is a fixed monthly cost
that is already budgeted. Fare changes disrupt a planned budget.

Personality vector base ranges:
- income_monthly: ₹18,000 – ₹45,000
- income_stability: 0.72 – 0.88
- commute_dependency: 0.74 – 0.88
- loss_aversion_score: 0.71 – 0.82
- savings_buffer_days: 15 – 45
- work_location_stability: 0.78 – 0.92 (fixed office/factory)
- family_financial_dependents: 1 – 3
- loan_obligation_flag: 0.55 – 0.75 (likely has EMI — home, vehicle, or phone)
- digital_access_level: 0.61 – 0.78

Decision logic specifics:
★ TRANSIT DECISION: Compares total monthly transport cost as
  percentage of take-home salary. Threshold: if transport exceeds
  12% of monthly salary, begins evaluating alternatives.
  Unlike daily wage worker, has time to plan — response is delayed
  by 7-14 days as agent recalculates monthly budget.
★ LOAN SENSITIVITY: If loan_obligation_flag is high AND fare
  increases push transport above threshold, financial stress index
  spikes sharply. Agent begins requesting loan restructuring
  information from financial institution agents.
★ SOCIAL BROADCAST: Primarily workplace social network. Information
  about fare changes spreads through office WhatsApp groups —
  mostly factual sharing, low emotional amplification.
★ COLLECTIVE ACTION: Moderate willingness. Will sign petitions,
  share protest posts. Lower physical protest participation than
  daily wage workers. Higher likelihood of formal complaint filing.
★ EXAMINATION RELEVANCE: High — children's examination outcomes
  are a primary life priority for this archetype. Examination
  policy changes trigger strong response.

Real-world zones where this archetype dominates:
DEL_EAST, DEL_WEST, MUM_KURLA, MUM_CHEMBUR, BLR_NORTH,
CHN_NORTH, HYD_KUKATPALLY, KOL_NORTH

---

### ARCHETYPE 3: GOVERNMENT EMPLOYEE
Hindi term: sarkari karmchari

Profile:
Central or state government servant. Fixed salary with pension.
Highly job-secure. Transit subsidy may apply (railway pass, etc.).
Often lives in government colony with proximity to workplace.
Different relationship with government institutions than other archetypes —
trusts government more, criticises government more carefully.

Personality vector base ranges:
- income_monthly: ₹25,000 – ₹85,000 (wide range, grade-dependent)
- income_stability: 0.95 – 0.99 (highest of all archetypes)
- institutional_trust_railways: 0.68 – 0.82 (higher than average)
- institutional_trust_examinations: 0.71 – 0.88
- transit_subsidy_flag: 0.45 – 0.70 (may have railway/metro pass)
- political_expression_restraint: 0.65 – 0.85 (less likely to protest publicly)
- commute_dependency: 0.55 – 0.75 (many live near workplace)
- pension_security_index: 0.88 – 0.98

Decision logic specifics:
★ TRANSIT DECISION: If transit_subsidy_flag is active, fare hike
  has zero direct impact. Agent is immune to fare changes during
  subsidy period. This creates a visible split in simulation —
  government employees buffer the aggregate resistance numbers.
★ SUBSIDY REMOVAL SCENARIO: If policy removes transit subsidy,
  this archetype transitions to the highest resistance category
  immediately — perceived betrayal amplifier.
★ EXAMINATION RESPONSE: Strong support for examination integrity.
  NEET leak scenario triggers high distrust response — government
  employee parents hold the board to a higher standard.
★ SOCIAL BROADCAST: Lower amplitude but high credibility broadcast.
  When a government employee expresses distrust, it carries more
  weight in connected networks than a daily wage worker expressing
  the same distrust.
★ COLLECTIVE ACTION: Very low physical protest. High formal
  grievance filing. Service association representation.

Real-world zones where this archetype dominates:
DEL_NEWDELHI, DEL_CENTRAL, CHN_CENTRAL, HYD_SECUNDERABAD,
KOL_CENTRAL, DEL_NORTH (Civil Lines)

---

### ARCHETYPE 4: TECH / KNOWLEDGE WORKER
Hindi term: software-wala (colloquial in simulation logs)

Profile:
Software engineer, data analyst, product manager, UX designer.
High income. High digital access. Works in IT park or hybrid/remote.
Transit is a quality-of-life decision, not a survival decision.
Fare sensitivity is low. Service quality sensitivity is high.

Personality vector base ranges:
- income_monthly: ₹60,000 – ₹350,000
- income_stability: 0.82 – 0.94
- commute_dependency: 0.28 – 0.55 (WFH option available)
- fare_sensitivity_score: 0.08 – 0.22 (lowest of all archetypes)
- service_quality_sensitivity: 0.78 – 0.92 (high — comfort matters)
- digital_access_level: 0.92 – 0.99
- political_expression_online: 0.71 – 0.88 (Twitter/X, LinkedIn active)
- cab_aggregator_dependency: 0.45 – 0.75 (Ola/Uber as transit alternative)

Decision logic specifics:
★ TRANSIT DECISION: Does NOT calculate fare as percentage of income
  (fare is trivial). Instead evaluates: comfort, reliability,
  time cost. A 30-minute delay is a stronger switch trigger
  than a 50% fare increase.
★ WFH LEVER: When transit service quality drops, first response
  is to invoke WFH rather than switch mode. This makes this
  archetype nearly invisible in ridership impact numbers while
  being highly vocal in political/social media impact.
★ CAB ALTERNATIVE: Has Ola/Uber as a live alternative. When
  metro/rail fare increases, cab_aggregator_dependency rises.
  This has secondary effects — cab demand surge in IT corridors.
★ SOCIAL BROADCAST: Extremely high amplitude online broadcast.
  One tech worker's LinkedIn post about a policy failure reaches
  hundreds of connected professionals. Primary driver of
  English-language media coverage in simulation.
★ EXAMINATION RELEVANCE: High — extremely competitive about
  children's examination outcomes. NEET/JEE policy changes
  trigger intense online advocacy.
★ COLLECTIVE ACTION: Almost never physical protest. Extremely
  active online petition, media coverage generation, and
  political amplification. Creates the "Twitter storm" dynamic
  in simulation.

Real-world zones where this archetype dominates:
BLR_WHITEFIELD, BLR_ELECTRONIC_CITY, BLR_OUTER_RING,
MUM_BANDRA (west), CHN_OMR, HYD_HITECH, DEL_NCR_GURGAON

---

### ARCHETYPE 5: SMALL BUSINESS OWNER / TRADER
Hindi term: vyapari

Profile:
Runs a shop, small manufacturing unit, or trade business.
Income depends on footfall and supply chain. Transit policy affects
both — customers need to reach the shop AND supply needs to arrive.
Has employees whose commute also matters. Complex multi-vector
sensitivity to transit policy.

Personality vector base ranges:
- income_monthly: ₹25,000 – ₹180,000 (highly variable)
- income_stability: 0.35 – 0.62 (moderate — seasonal + footfall dependent)
- footfall_transit_dependency: 0.45 – 0.85
- employee_count: 1 – 15
- supply_chain_transit_dependency: 0.38 – 0.72
- risk_tolerance: 0.42 – 0.68 (higher than wage workers — entrepreneurial)
- loss_aversion_score: 0.62 – 0.78
- political_network_connections: 0.45 – 0.72 (knows local councillor)

Decision logic specifics:
★ TRANSIT DECISION: Does not make a simple personal commute
  decision. Evaluates: will my customers reach me? Will my
  suppliers reach me? Will my employees show up? Three separate
  calculations, then aggregates.
★ FOOTFALL IMPACT: When transit disruption or fare hike causes
  measurable footfall drop (>15% in 3 days), agent begins
  evaluating: temporary closure, reduced hours, or rent
  renegotiation. This triggers informal economy cascade.
★ EMPLOYEE SENSITIVITY: If fare hike pushes employee commute
  cost above threshold, vyapari agent faces pressure to
  either raise wages (cutting margin) or lose staff.
★ POLITICAL NETWORK: Has direct connection to local Tier 2
  political agents. Faster escalation path than other archetypes.
  Complaint reaches local councillor within 3-5 simulation days.
★ COLLECTIVE ACTION: High organisation capacity. Trader
  associations activate quickly. Bandh (shutdown) threats are
  a unique action available only to this archetype.
★ EXAMINATION RELEVANCE: Moderate — coaching centre owners are
  a sub-variant of this archetype with much higher examination
  sensitivity.

Real-world zones where this archetype dominates:
MUM_DHARAVI, DEL_SHAHDARA, KOL_CENTRAL, CHN_NORTH,
HYD_OLDCITY, BLR_WEST (Malleshwaram market)

---

### ARCHETYPE 6: STUDENT
Hindi term: vidyarthi

Profile:
Full-time student — school (class 9-12) or college/university.
Not earning. Dependent on family income for commute costs.
Transit policy affects daily college attendance. Examination policy
is the single most important policy domain for this archetype.
Highly networked with other students. High social media activity.

Personality vector base ranges:
- personal_income: 0 (dependent)
- family_income_bracket: inherited from parent agent if linked,
  else sampled from zone income distribution
- transit_cost_family_burden: 0.55 – 0.85
- examination_sensitivity: 0.88 – 0.98 (highest of all archetypes)
- political_engagement: 0.45 – 0.72 (rises sharply post-NEET)
- peer_influence_susceptibility: 0.72 – 0.88 (high — social proof matters)
- coaching_centre_dependency: 0.35 – 0.78 (JEE/NEET preparation)
- online_protest_propensity: 0.78 – 0.92
- physical_protest_propensity: 0.55 – 0.75

Decision logic specifics:
★ TRANSIT DECISION: Does not make own transit decision.
  Decision is made at family level — parent archetype absorbs
  the cost calculation. Student agent only records the outcome:
  attendance_maintained or attendance_reduced.
  BUT: student agent independently evaluates whether to join
  a carpooling group or use college bus if fare hike is discussed
  in peer network.
★ EXAMINATION RESPONSE: The most reactive archetype to examination
  policy changes. Trust index drops faster and deeper than any
  other archetype when examination integrity is questioned.
  Recovery is also slowest — trust lost by NEET 2024 has not
  recovered in 2025 for this archetype.
★ PEER CASCADE: Student agents are the fastest-cascading archetype.
  When one student in a peer cluster changes behaviour or opinion,
  peer_influence_susceptibility means 60-80% of the cluster
  updates within 2-3 simulation days.
★ COLLECTIVE ACTION: Highest physical protest propensity after
  daily wage workers. Student protests are uniquely visible in
  simulation — media coverage multiplier activates.
★ COACHING CENTRE NODE: Students with coaching_centre_dependency
  > 0.6 have a secondary commute trip per day. Fare hikes
  create a double cost hit for this sub-group.

Real-world zones where this archetype dominates:
DEL_NORTH (Delhi University belt), BLR_CENTRAL (Jayanagar),
CHN_SOUTH (Adyar, T Nagar), HYD_CENTRAL, KOL_JADAVPUR,
MUM_ANDHERI (coaching belt)

---

### ARCHETYPE 7: HOMEMAKER / HOUSEHOLD MANAGER
Hindi term: grihini

Profile:
Primary household manager, typically not in formal employment.
Makes daily decisions about household provisioning, children's
transport, and family logistics. Transit policy affects cost of
daily errands, children's school commute, and access to markets.
Often overlooked in policy analysis. Critical in simulation because
homemaker agents are the primary drivers of local market footfall
and school attendance decisions.

Personality vector base ranges:
- personal_income: 0 (household role)
- household_management_scope: 0.72 – 0.95
- children_count: 1 – 4
- school_commute_responsibility: 0.65 – 0.88
- daily_market_transit_frequency: 3 – 7 trips per week
- local_community_network_strength: 0.78 – 0.92 (highest of all archetypes)
- price_sensitivity: 0.82 – 0.94
- information_broker_role: 0.65 – 0.82

Decision logic specifics:
★ TRANSIT DECISION: Makes decisions for entire household, not just
  self. When fare rises, evaluates: children's school commute cost,
  daily market trip cost, total household transport budget.
  Decision is to restructure all household trips simultaneously.
★ MARKET FOOTFALL IMPACT: Homemaker agents are the primary source
  of footfall for local markets. When transit cost rises, trip
  consolidation begins — 5 separate market trips become 2.
  This is the mechanism that collapses footfall at informal
  economy nodes in the simulation.
★ SCHOOL ATTENDANCE LINK: Homemaker agent decision to walk
  children to school (instead of auto/bus) creates a visible
  spike in school_walking_distance metric. For distances above
  2km, attendance drops. This feeds into examination scenario.
★ INFORMATION NETWORK: Homemaker agents are the highest-density
  information nodes in residential zones. Local network strength
  of 0.78-0.92 means their broadcast about price changes reaches
  almost every neighbour within 2-3 days. They are the
  neighbourhood's informal information infrastructure.
★ COLLECTIVE ACTION: Low physical protest. Very high community
  organising — petition signing, RWA meetings, school parent
  group mobilisation.

Real-world zones where this archetype dominates:
All residential zones. Highest concentration: DEL_NORTHWEST
(Rohini), MUM_BORIVALI, MUM_VASAI, BLR_NORTH, CHN_WEST,
HYD_KUKATPALLY, KOL_NORTH

---

### ARCHETYPE 8: STREET VENDOR / HAWKER
Hindi term: pheriwala / rehri-wala

Profile:
Informal sector vendor. Sells from a fixed or mobile location.
Extremely high transit dependency — must reach vending location
daily AND goods supply must reach them. No formal employment
protection. Income is purely footfall-dependent. Among the most
vulnerable archetypes to any transit disruption.

Personality vector base ranges:
- income_monthly: ₹6,000 – ₹22,000
- income_daily_variability: 0.45 – 0.72 (high day-to-day variance)
- vending_location_transit_dependency: 0.88 – 0.98
- goods_supply_transit_dependency: 0.65 – 0.82
- savings_buffer_days: 0 – 5
- police_interaction_risk: 0.35 – 0.65 (informal location legality)
- loss_aversion_score: 0.88 – 0.97 (second highest after daily wage)
- community_network_strength: 0.72 – 0.88 (vendor associations)

Decision logic specifics:
★ TRANSIT DECISION: Must reach vending spot. Non-negotiable.
  When fare exceeds 10% of expected daily income, agent evaluates
  relocating vending spot to reduce commute distance.
  Spot relocation has cascading effects — customer loss,
  police encounter probability, income drop during transition.
★ SUPPLY CHAIN: If goods arrive by transit (vegetable vendors,
  garment vendors), supply cost also rises with fare hike.
  Double cost impact unique to this archetype.
★ TRANSIT DISRUPTION: Any transit disruption causes immediate
  income loss (unlike formal employees who may WFH). This makes
  street vendors the simulation's most sensitive leading indicator
  of transit policy impact.
★ COMPOUND VULNERABILITY: In Mumbai scenarios, many vendors
  operate near station exits. Metro/rail disruption collapses
  both their ability to arrive AND their customer base simultaneously.
★ COLLECTIVE ACTION: Vendor associations activate quickly.
  Physical protest propensity is high when income is directly
  threatened. Dharna at municipal office is a unique action.

Real-world zones where this archetype dominates:
MUM_DHARAVI, MUM_KURLA, DEL_SHAHDARA, DEL_NORTHEAST,
KOL_CENTRAL (Sealdah market area), CHN_NORTH, HYD_OLDCITY

---

### ARCHETYPE 9: RETIRED / SENIOR CITIZEN
Hindi term: pensioner / buzurg

Profile:
Retired, 60+. Fixed pension or family support income.
Transit use is primarily for medical appointments, social visits,
and leisure. Not commute-driven. Senior citizen concession
fares are a key policy sensitivity — removal of concession is
a uniquely sharp trigger for this archetype.
High social credibility in network broadcasts.

Personality vector base ranges:
- income_monthly: ₹8,000 – ₹45,000 (pension dependent)
- income_type: pension / family_support / investment_returns
- transit_frequency: 2 – 5 trips per week (lower than average)
- senior_concession_dependency: 0.55 – 0.85
- health_transit_dependency: 0.45 – 0.72 (hospital access critical)
- social_network_credibility: 0.78 – 0.92 (high trust in local network)
- technology_adoption: 0.18 – 0.42 (lower digital access)
- institutional_memory: 0.85 – 0.95 (remembers past policy changes)
- political_voting_propensity: 0.88 – 0.97 (highest voter turnout archetype)

Decision logic specifics:
★ TRANSIT DECISION: Unique trigger: senior_citizen_concession_removal
  is the single most activating policy event for this archetype.
  More activating than a 30% standard fare hike.
  Health_transit_dependency means even after deciding against
  recreational transit, medical appointment trips are maintained
  at high personal cost — creating visible health expenditure stress.
★ INSTITUTIONAL MEMORY: This archetype references historical policy
  events in its reasoning. "The 2015 fare hike also started at 20%
  and became 35% within 18 months." This memory-driven scepticism
  amplifies resistance to new policies — unique to this archetype.
★ SOCIAL BROADCAST: High credibility, low speed. One senior
  citizen's opinion in an RWA meeting influences 15-30 neighbours
  over 5-7 days. Slower than digital broadcast but more durable.
★ POLITICAL LEVERAGE: Highest voting propensity. Tier 2 political
  agents give disproportionate weight to senior citizen sentiment.
  When senior citizen cluster resistance rises, local politician
  agents respond faster than for any other archetype.
★ COLLECTIVE ACTION: Letter campaigns, RWA petitions, media
  interviews. Physical protest is low but media engagement is high.

Real-world zones where this archetype dominates:
DEL_SOUTH (Saket, GK), MUM_SOUTHMUMBAI, BLR_SOUTH (Jayanagar),
CHN_WEST (Anna Nagar), KOL_SOUTH (Ballygunge)

---

### ARCHETYPE 10: MIGRANT WORKER
Hindi term: pravasi majdoor

Profile:
Worker who has migrated from another state or district.
Remits a significant portion of income to home family.
No permanent housing near workplace — lives in shared accommodation
far from worksite. Multiple jobs or gig economy work.
Transit dependency is extreme. Has no alternative to transit
because walking distance from accommodation to worksite is
typically 10-25km.

Personality vector base ranges:
- income_monthly: ₹10,000 – ₹28,000
- remittance_rate: 0.35 – 0.65 (portion sent home monthly)
- disposable_income_actual: income × (1 - remittance_rate)
- home_state: sampled from Bihar, UP, Rajasthan, Odisha, Jharkhand,
              MP, WB (source state distribution from Census migration data)
- housing_type: shared_room | labour_camp | pavement
- social_network_type: hometown_cluster (primary connection is
  to others from same village/district)
- documentation_completeness: 0.35 – 0.72 (affects institutional access)
- crisis_vulnerability_index: 0.82 – 0.96 (highest of all archetypes)
- return_migration_threshold: 0.78 – 0.92

Decision logic specifics:
★ TRANSIT DECISION: Cannot walk to work. Cannot afford cab.
  When fare exceeds disposable_income threshold (not gross income),
  the agent evaluates return_migration: going back to home state.
  This is the unique action of this archetype — vanishing from
  the city's labour pool entirely. Happened during COVID.
  Happens at smaller scale with large fare hikes.
★ REMITTANCE CONSTRAINT: Fare calculation uses disposable income
  (after remittance), not gross income. This makes migrant workers
  2-3x more fare sensitive than their gross income suggests.
★ HOMETOWN CLUSTER NETWORK: Social network is clustered by
  origin state/district. Information spreads through this cluster
  extremely fast — faster than any other archetype. One worker
  deciding to return home triggers cascade within the cluster.
★ RETURN MIGRATION CASCADE: If 15%+ of a hometown cluster activates
  return_migration behaviour, remaining cluster members receive
  strong return signal. Labour pool collapse is an emergent
  simulation outcome unique to this archetype.
★ COLLECTIVE ACTION: Very low — documentation concerns, no union
  membership, fear of losing work. But return migration is itself
  a form of collective action that has enormous policy impact.

Real-world zones where this archetype dominates:
MUM_DHARAVI, MUM_KURLA, DEL_NORTHEAST, BLR_PERIURBAN,
CHN_AMBATTUR, HYD_OLDCITY (construction belt), KOL_HOWRAH

---

### ARCHETYPE 11: HEALTHCARE WORKER
Hindi term: swasthya karmchari

Profile:
Doctor, nurse, technician, ward boy, ambulance driver.
Shift-based work — includes night shifts and early morning shifts
when public transit is unavailable or reduced frequency.
Transit disruption has direct public health consequences beyond
personal impact — a nurse who cannot reach hospital affects patient care.
High institutional trust in government systems (employer).

Personality vector base ranges:
- income_monthly: ₹15,000 – ₹180,000 (wide — ward boy to specialist)
- shift_pattern: day_shift | night_shift | rotating
- night_transit_dependency: 0.72 – 0.92 (critical — fewer options at night)
- institutional_trust_government: 0.68 – 0.82
- essential_worker_identity: 0.82 – 0.95 (strong professional identity)
- policy_impact_multiplier: 1.4
  (decisions affecting this archetype have 1.4x media amplification
   — "nurses unable to reach hospital" generates disproportionate coverage)

Decision logic specifics:
★ TRANSIT DECISION: Cannot use WFH lever. Cannot miss shift.
  Night shift workers evaluate: shared auto, cycling, employer
  transport. If none available, shift_missed_flag activates —
  which triggers a downstream patient_care_impact event.
★ NIGHT TRANSIT VULNERABILITY: After 11pm, metro/bus frequency
  drops. For rotating shift workers, the simulation models
  reduced transit options explicitly. Fare hike compounds
  an already constrained choice set.
★ POLICY AMPLIFICATION: When healthcare workers are visibly
  affected by a transit policy, media coverage multiplier
  activates at 1.4x. Journalists specifically seek out this
  archetype for impact stories. Tier 2 journalist agents
  prioritise healthcare worker signals.
★ COLLECTIVE ACTION: Professional unions (IMA, nursing unions)
  activate on behalf of this archetype. Unique escalation
  path to health ministry, not just transport ministry.

Real-world zones where this archetype dominates:
All zones near major hospitals. Specifically:
DEL_CENTRAL (AIIMS belt), MUM_CENTRAL (KEM, Sion hospital zone),
CHN_CENTRAL (Government General Hospital), KOL_NORTH (SSKM),
HYD_CENTRAL (Osmania Hospital), BLR_CENTRAL (Victoria Hospital)

---

### ARCHETYPE 12: STUDENT APPEARING FOR COMPETITIVE EXAM
(JEE / NEET / UPSC / state PSC)
Hindi term: aspirant

Profile:
Full-time exam preparation student. No income. Extremely high
examination sensitivity — the highest of any archetype.
Often relocated from home state to coaching hub city (Kota,
Delhi, Hyderabad). Lives in hostel or PG accommodation.
Daily schedule is dominated by coaching centre trips.

Personality vector base ranges:
- personal_income: 0
- family_financial_pressure: 0.72 – 0.94 (family has invested heavily)
- examination_sensitivity: 0.95 – 0.99 (absolute maximum)
- attempts_remaining: 1 – 3 (affects stress level dramatically)
- coaching_centre_trips_per_day: 1 – 2
- peer_comparison_anxiety: 0.78 – 0.95
- social_isolation_index: 0.55 – 0.78 (cut off from home social network)
- mental_health_stress_index: 0.65 – 0.88
- information_source_trust: coaching_teacher > peer > parent > media
  (unique trust ordering — coach is highest credibility source)

Decision logic specifics:
★ TRANSIT DECISION: Coach centre is non-negotiable destination.
  When transit is disrupted, walks if within 3km, shares auto if
  within 6km. Income is zero so family budget absorbs all costs.
  This creates a family archetype (vyapari or formal employee)
  receiving the financial shock, not the aspirant directly.
★ EXAMINATION POLICY RESPONSE: Most sensitive archetype to any
  NTA/CBSE/UPSC announcement. Trust collapse spreads instantly
  through aspirant peer network — faster than any other archetype.
  A single credible rumour of paper leak can collapse collective
  exam preparation motivation within 48 simulation hours.
★ MENTAL HEALTH CASCADE: Unique to this archetype. When
  examination_sensitivity is very high AND a leak/cancellation
  event occurs, mental_health_stress_index spikes. This does
  not directly affect other simulation metrics but it is
  logged as a welfare indicator output of the simulation.
★ COACHING ECONOMY: Aspirant agents are the primary economic
  input for coaching centre nodes (a sub-type of vyapari agents).
  Examination cancellations cause coaching centre revenue collapse
  within 5-7 simulation days.

Real-world zones where this archetype dominates:
DEL_NORTH (Mukherjee Nagar, UPSC belt), DEL_CENTRAL (Rajinder
Nagar coaching belt), HYD_CENTRAL (UPSC/state PSC prep zone),
CHN_SOUTH (TNPSC prep belt), KOL_NORTH (PSC prep zone)

---

### ARCHETYPE 13: GIG ECONOMY WORKER
Hindi term: gig-worker / app-based worker

Profile:
Ola/Uber driver, Swiggy/Zomato delivery, Urban Company service
worker, freelance logistics. Income is per-trip or per-task.
Transit policy affects both their cost of operating AND their
demand (customers order less when transit costs rise, customers
order more when transit is disrupted).

Personality vector base ranges:
- income_monthly: ₹18,000 – ₹55,000 (platform dependent)
- income_variability: 0.52 – 0.78 (high — surge and drought patterns)
- vehicle_type: two_wheeler | four_wheeler | bicycle
- fuel_cost_sensitivity: 0.72 – 0.88
- platform_dependency: 0.78 – 0.94 (income entirely from one platform)
- transit_fare_indirect_sensitivity: 0.45 – 0.68
  (when public transit fares rise, cab demand rises — increases their income)
  (when fuel prices rise, their cost rises — complex bidirectional relationship)
- loan_on_vehicle: 0.55 – 0.78 (most gig vehicles are on EMI)

Decision logic specifics:
★ TRANSIT DECISION: Unique bidirectional response.
  When public transit fare rises: cab demand rises → gig income rises.
  When fuel prices rise: operating cost rises → net income falls.
  This archetype is the only one that can BENEFIT from a public
  transit fare hike — making their response fundamentally different.
★ TRANSIT DISRUPTION: A railway strike is a windfall event for
  cab and delivery gig workers — demand surges. Simulation
  models this surge and the cab price spike that follows.
  Secondary effect: cab surge pricing further hurts daily wage
  workers who had switched to cab as transit alternative.
★ PLATFORM POLICY SENSITIVITY: App policy changes (commission
  rate increases) are as important as government policy for
  this archetype. Not in scope for MVP but noted for future.
★ VEHICLE LOAN VULNERABILITY: If income drops below vehicle
  EMI threshold for 2+ weeks, agent flags loan default risk.
  This creates a financial sector cascade opportunity.
★ COLLECTIVE ACTION: New category — platform strikes. App
  worker associations have demonstrated collective action
  (Ola driver strikes, Zomato delivery boycotts). Unique
  action type separate from transport fare protests.

Real-world zones where this archetype dominates:
All zones. Highest concentration near transit hubs:
MUM_ANDHERI, DEL_EAST, BLR_WHITEFIELD (delivery demand),
HYD_HITECH (cab demand), CHN_OMR

---

### ARCHETYPE 14: JOURNALIST / MEDIA WORKER
(Tier 1 version — local/freelance media)
Hindi term: patrakar

Profile:
Local reporter, freelance journalist, social media content creator,
community radio worker. Not the Tier 2 journalist agent (who is
a full opinion leader). This Tier 1 version is a regular citizen
who also has a media production capability. Their transit decisions
are ordinary. But their social broadcast has a multiplier.

Personality vector base ranges:
- income_monthly: ₹15,000 – ₹65,000
- media_reach_multiplier: 2.5 – 8.0
  (broadcasts reach 2.5x–8x more agents than standard Tier 1)
- publication_type: local_newspaper | online_portal | youtube |
                    twitter | community_radio
- editorial_independence: 0.35 – 0.82
- political_alignment: sampled from zone political distribution
- field_access_zones: list of zones this journalist covers
- source_network_strength: 0.65 – 0.88

Decision logic specifics:
★ TRANSIT DECISION: Standard formal_sector_employee logic for
  personal commute decisions. Nothing special.
★ SOCIAL BROADCAST: The only Tier 1 archetype with a broadcast
  multiplier. When this agent decides to file a story, their
  broadcast reaches media_reach_multiplier × standard connections.
  A freelance journalist with reach_multiplier 6.0 filing a
  story about a fare hike impacts 240 agents instead of 40.
★ STORY TRIGGER: Agent evaluates whether current events cross
  the newsworthiness threshold based on:
  - personal impact (did it affect me?)
  - community impact (how many connections are affected?)
  - novelty (is this a new development?)
  - political angle (does this have an editorial angle my
    publication will run?)
★ FEEDBACK LOOP: Journalist broadcast → wider awareness → more
  agents update opinions → journalist detects more community
  impact → more stories filed. This self-reinforcing loop
  creates media coverage cascades in the simulation.

Real-world zones where this archetype appears:
All zones. Local journalists are distributed across every
zone with a small density (0.8-1.5% of zone population).

---

## ARCHETYPE DISTRIBUTION BY ZONE TYPE

### Dense Low-Income Zone (example: DEL_NORTHEAST, MUM_DHARAVI)
daily_wage_worker:          0.28
street_vendor:              0.12
migrant_worker:             0.18
homemaker:                  0.14
formal_sector_employee:     0.11
small_business_owner:       0.08
student:                    0.06
gig_economy_worker:         0.02
retired:                    0.01
journalist_tier1:           0.00 (trace)
total:                      1.00

### Middle Income Residential (example: DEL_WEST, MUM_KURLA)
formal_sector_employee:     0.31
homemaker:                  0.16
student:                    0.13
daily_wage_worker:          0.11
small_business_owner:       0.10
gig_economy_worker:         0.07
government_employee:        0.06
retired:                    0.04
migrant_worker:             0.02
journalist_tier1:           0.01 (trace)
total:                      1.01 → normalise to 1.00

### High Income / Professional (example: BLR_WHITEFIELD, MUM_BANDRA)
tech_knowledge_worker:      0.38
formal_sector_employee:     0.18
homemaker:                  0.12
student:                    0.10
retired:                    0.06
small_business_owner:       0.07
gig_economy_worker:         0.05
government_employee:        0.03
journalist_tier1:           0.01
total:                      1.00

### Government Zone (example: DEL_NEWDELHI, DEL_CENTRAL)
government_employee:        0.42
formal_sector_employee:     0.18
homemaker:                  0.12
retired:                    0.08
student:                    0.07
small_business_owner:       0.06
tech_knowledge_worker:      0.04
journalist_tier1:           0.02
daily_wage_worker:          0.01
total:                      1.00

### IT Corridor (example: BLR_ELECTRONIC_CITY, CHN_OMR)
tech_knowledge_worker:      0.52
gig_economy_worker:         0.14
formal_sector_employee:     0.12
homemaker:                  0.08
student:                    0.06
small_business_owner:       0.05
journalist_tier1:           0.02
daily_wage_worker:          0.01
total:                      1.00

### Examination Hub (example: DEL_NORTH, HYD_CENTRAL)
student:                    0.18
exam_aspirant:              0.22
formal_sector_employee:     0.20
homemaker:                  0.14
small_business_owner:       0.12
government_employee:        0.08
daily_wage_worker:          0.04
journalist_tier1:           0.02
total:                      1.00

### Transit Hub / Mixed (example: MUM_ANDHERI, DEL_SHAHDARA)
formal_sector_employee:     0.24
daily_wage_worker:          0.16
homemaker:                  0.13
gig_economy_worker:         0.11
small_business_owner:       0.10
student:                    0.09
migrant_worker:             0.08
street_vendor:              0.05
retired:                    0.03
journalist_tier1:           0.01
total:                      1.00

### Industrial Zone (example: CHN_AMBATTUR, KOL_HOWRAH)
formal_sector_employee:     0.35
daily_wage_worker:          0.24
migrant_worker:             0.18
homemaker:                  0.12
small_business_owner:       0.06
gig_economy_worker:         0.03
student:                    0.02
total:                      1.00

### Periurban / Low Connectivity (example: BLR_PERIURBAN, MUM_VASAI)
homemaker:                  0.22
daily_wage_worker:          0.21
formal_sector_employee:     0.18
small_business_owner:       0.12
migrant_worker:             0.10
student:                    0.09
street_vendor:              0.05
retired:                    0.03
total:                      1.00

---

## HOW ARCHETYPES INTERACT IN THE SOCIAL NETWORK

Not all archetypes connect equally. The social network edges
are archetype-aware.

★ Daily wage worker ↔ Daily wage worker: HIGH connection probability
  (worksite networks, labour contractor groups)
★ Homemaker ↔ Homemaker: HIGH (colony networks, school parent groups)
★ Tech worker ↔ Tech worker: HIGH (office networks, online communities)
★ Student ↔ Student: HIGH + FAST (peer networks, coaching groups)
★ Migrant worker ↔ Migrant worker (same origin state): VERY HIGH
  (hometown cluster networks)
★ Vyapari ↔ Daily wage worker: HIGH (employer-employee proximity)
★ Journalist (Tier 1) ↔ All archetypes: MODERATE (covers all zones)
★ Government employee ↔ Tech worker: LOW (different worlds)
★ Street vendor ↔ Homemaker: HIGH (daily market interaction)
★ Aspirant ↔ Aspirant: VERY HIGH + VERY FAST (coaching cohort)
★ Healthcare worker ↔ All archetypes: LOW direct, HIGH mediated
  (contact with many but deep connection with few)
★ Retired ↔ Homemaker: HIGH (neighbourhood proximity, RWA)
★ Gig worker ↔ Daily wage worker: MODERATE (economic proximity)

Cross-archetype connections:
★ Vyapari → Local politician Tier 2: DIRECT (business community link)
★ Aspirant → Coaching owner Tier 2: DIRECT (student-teacher)
★ Healthcare worker → Hospital administrator Tier 2: DIRECT
★ Journalist Tier 1 → Journalist Tier 2: DIRECT (professional network)

---

## AGENT FACTORY — ARCHETYPE INSTANTIATION

### How the factory uses archetypes

AgentFactory.spawn_agents(zone_context, n_agents):

1. Read zone's tier1_agent_archetype_weights
   (zone config overrides the zone-type default above)

2. For each archetype slot:
   a. Load archetype base template
      (decision logic class, parameter bounds, available actions)
   b. Sample personality vector within archetype bounds
      using zone income distribution as constraint
   c. Assign life context:
      - daily_wage_worker: assign contractor_network_id
      - student: optionally link to parent agent if spawning families
      - migrant_worker: assign origin_state from census migration data
      - aspirant: assign attempts_remaining, coaching_centre_node
      - gig_worker: assign platform_type, vehicle_type
   d. Seed 30-day memory with archetype-appropriate history
      - worker: commute delay events, income fluctuation events
      - student: examination schedule events, peer events
      - homemaker: market price events, school schedule events
      - retired: health appointment events, social events

3. Build social network edges respecting archetype affinity matrix
   (archetype pairs with HIGH affinity get more edges between them)

4. Assign Tier 2 hub agents from zone's tier2_agent_types
   as high-degree nodes in the network

5. Validate population:
   - archetype distribution matches zone weights within 2%
   - income distribution matches zone income profile within 3%
   - network degree distribution follows scale-free property
   - each archetype's available_actions are correctly loaded

---

## SAMPLE MULTI-ARCHETYPE INTERACTION: 20% FARE HIKE IN DEL_SHAHDARA

Day 1 — Policy announced:
★ Daily wage workers (28% of zone): calculate daily cost impact.
  41% immediately flag switch evaluation. 12% flag return to
  walking for short legs.
★ Homemakers (14%): recalculate household transport budget.
  Begin trip consolidation. Market visit frequency drops.
★ Street vendors (5%): double cost hit — personal commute AND
  goods supply. Viability flag activates for 23% of vendors.
★ Gig workers (4%): cab demand rises as some transit users switch.
  Income projection improves. No resistance from this archetype.
★ Tech workers (3%): fare is irrelevant. No behaviour change.
  BUT: online platform activity rises — Twitter commentary begins.

Day 3 — Network propagation:
★ Homemaker network broadcasts market cost impact to 340 connected
  homemakers across zone. Footfall decline at 4 market nodes
  begins.
★ Daily wage workers in contractor group receive WhatsApp message
  about fare hike impact from 6 connections who have already
  switched. Cascade threshold approaching.

Day 7 — Secondary effects:
★ Street vendor at Node SHAHDARA_MARKET_1 logs 18% footfall drop.
  Viability threshold crossed. Agent evaluates reduced hours.
★ Vyapari at market node detects footfall drop in accounts.
  Files complaint to local councillor Tier 2 agent.
★ Tech workers (small fraction, 3% of zone): 0 transport behaviour
  change but 5 journalist Tier 1 agents have filed stories.
  Media coverage multiplier activates.

Day 11 — Collective action emergence:
★ Daily wage worker collective_action_threshold (0.38) crossed
  in northeast cluster of zone. Coalition formation event logged.
★ Local union representative Tier 2 agent detects threshold
  breach. Autonomously broadcasts resistance signal.
★ 127 additional Tier 1 agents update resistance score.
★ Protest probability index crosses 35% threshold.
★ Government Agent fires autonomous alert.

Day 14 — Archetype-differentiated resolution:
★ Daily wage workers: 31% have permanently switched mode or route.
★ Homemakers: consolidated trips by 38%. Market footfall at -24%.
★ Street vendors: 11% have relocated vending spot.
★ Migrant workers: 8% have activated return_migration evaluation.
★ Aspirants: no transit change but 3 exam centres now harder to
  reach — coaching attendance drop of 6% logged.
★ Retired: 22% have reduced non-essential transit. Health
  appointment maintenance but social visit reduction.
★ Gig workers: income up 12% from cab demand surge. Counter-signal
  in resistance index from this archetype.

AGGREGATE RESULT:
Protest probability: 38% (threshold exceeded)
Modal shift: 19% from rail to other modes
Revenue impact: -14% vs pre-hike baseline
Informal economy footfall: -22% at transit-adjacent nodes
Government Agent recommendation: phase to 10% over 60 days.
Projected resistance reduction: 58%.

This is what 14 archetypes produce that 1 archetype cannot:
a heterogeneous, realistic, recognisable city response.