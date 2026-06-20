# DRIFTWATCH — CITY PROFILE HIERARCHY

## Architecture Overview

STATE CONFIG
    ↓
CITY CONFIG
    ↓
ZONE CONFIG
    ↓
AGENT FACTORY reads zone config
    ↓
AGENTS generated with zone-specific parameters

## Why This Hierarchy

State config holds parameters that apply uniformly across all cities
in a state — political context, union law, language network, state
government trust. A fare hike in Delhi and Noida are both in different
states (Delhi UT vs UP) but adjacent geographically. The state layer
captures that difference without duplicating it in every city config.

City config holds parameters specific to the urban agglomeration —
transport network topology, aggregate ridership, city-level economic
baseline, validation anchors.

Zone config is where simulation accuracy actually lives. Dharavi and
Bandra West are in the same city. They are not the same simulation
environment. Every zone has its own income distribution, commute
pattern, informal employment rate, social network density, and
political sensitivity. Agents spawned from zone config behave like
people who actually live there.

---

## LAYER 1 — STATE CONFIG

### File naming: states/[state_code].json
### Examples: states/DL.json, states/MH.json, states/KA.json

### Schema
{
  "state_id": "DL",
  "state_name": "Delhi (NCT)",
  "language_primary": "Hindi",
  "language_secondary": ["Punjabi", "Urdu", "English"],
  "language_network_multiplier": 1.0,
    // How fast information spreads via language-homogeneous networks
    // Hindi-belt states: 1.0 baseline
    // Tamil Nadu: 1.3 (strong Tamil media ecosystem accelerates spread)
    // Kerala: 1.2

  "ruling_party_trust_index": float (0-1),
    // Source: Lokniti-CSDS State Assembly Survey post-election
    // Affects how state government policy announcements are received

  "union_legal_framework": "permissive" | "moderate" | "restrictive",
    // Permissive: West Bengal, Kerala — union activity legally protected
    // Restrictive: Gujarat, Rajasthan — essential services act applied broadly
    // Affects collective action threshold for all city agents in state

  "state_gdp_per_capita": number,
    // INR, current prices. Source: MoSPI state GDP estimates

  "state_informal_economy_share": float (0-1),
    // Source: NSSO PLFS state-level estimates

  "examination_board": "CBSE" | "state_board" | "both",
    // Determines which examination scenarios are relevant for this state

  "political_contestation_index": float (0-1),
    // 1.0 = highly contested (UP, Bihar), 0.3 = dominant party (Gujarat)
    // Source: margin-of-victory analysis from ECI 2024 data

  "media_penetration": {
    "tv": float,
    "print": float,
    "digital": float,
    "radio": float
  },
    // Source: BARC, ABC, Reuters Institute Digital News Report India

  "cities": ["DEL", "NOI", "GGN", "FBD"]
    // City IDs covered by this state config
}

### State Configs Required for Phase 1
states/DL.json    — Delhi NCT (covers Delhi city)
states/MH.json    — Maharashtra (covers Mumbai MMR)
states/KA.json    — Karnataka (covers Bengaluru)
states/TN.json    — Tamil Nadu (covers Chennai)
states/TS.json    — Telangana (covers Hyderabad)
states/WB.json    — West Bengal (covers Kolkata)

---

## LAYER 2 — CITY CONFIG

### File naming: cities/[city_code].json
### Examples: cities/DEL.json, cities/MUM.json

### Schema
{
  "city_id": "DEL",
  "city_name": "Delhi NCR",
  "state_id": "DL",
    // Parent state — city inherits all state-level parameters

  "population": 32900000,
  "area_sq_km": 1484,
  "ward_count": 272,

  "topology_type": "GRID" | "LINEAR" | "RADIAL" | "SPRAWL" | "POLYCENTRIC",
    // GRID: Delhi — relatively even policy impact distribution
    // LINEAR: Mumbai — bottleneck dynamics on rail corridors
    // SPRAWL: Bengaluru — high auto/bus dependency, weaker metro impact
    // POLYCENTRIC: Hyderabad — multiple CBDs, distributed impact

  "transport_network": {
    "metro_lines": [
      {
        "line_id": "YL",
        "name": "Yellow Line",
        "stations": 37,
        "daily_ridership": 420000,
        "corridor": "Samaypur Badli — HUDA City Centre",
        "data_source": "DMRC Annual Report 2023-24"
      }
      // ... all lines
    ],
    "suburban_rail": {
      "present": false
        // Delhi has no suburban rail — only metro + DTC buses
    },
    "bus_network": {
      "operator": "DTC + DIMTS",
      "route_count": 680,
      "daily_ridership": 3800000,
      "data_source": "DIMTS Annual Report 2022-23"
    },
    "total_daily_pt_ridership": 5200000
  },

  "economic_baseline": {
    "median_household_income_monthly": 28500,
      // INR. Source: NSSO 78th Round urban Delhi
    "gini_coefficient": 0.41,
      // Source: World Bank India Inequality Report
    "formal_employment_share": 0.54,
    "major_employment_sectors": ["government", "trade", "construction",
                                  "manufacturing", "hospitality"]
  },

  "osm_extract": {
    "source": "geofabrik",
    "url": "https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf",
    "bbox": [76.8, 28.4, 77.4, 28.9],
    "last_updated": "2024-01"
  },

  "validation_anchors": [
    {
      "anchor_id": "DEL_METRO_PH4",
      "description": "Delhi Metro Phase 4 ridership post-opening",
      "predicted": 340000,
      "actual": 318000,
      "error_pct": 6.9,
      "data_source": "DMRC 2024 published ridership"
    },
    {
      "anchor_id": "DEL_ODDEVEN_2016",
      "description": "Odd-even scheme traffic reduction",
      "predicted_range": [0, 5],
      "actual": 0,
      "outcome": "confirmed no significant reduction",
      "data_source": "IIT Delhi + TERI post-scheme analysis"
    }
  ],

  "confidence_grade": "A",
    // A: validated on 2+ anchors, rich data
    // B: 1 anchor or thin data
    // C: no anchors, lowest confidence

  "zones": ["DEL_NORTH", "DEL_SOUTH", "DEL_EAST", "DEL_WEST",
            "DEL_CENTRAL", "DEL_NORTHEAST", "DEL_NORTHWEST",
            "DEL_NEWDELHI", "DEL_SHAHDARA", "DEL_NCR_NOIDA",
            "DEL_NCR_GURGAON", "DEL_NCR_FARIDABAD"]
    // Zone IDs — each must have a corresponding zone config file
}

---

## LAYER 3 — ZONE CONFIG

### File naming: zones/[city_code]/[zone_id].json
### Examples: zones/DEL/DEL_SHAHDARA.json
###           zones/MUM/MUM_DHARAVI.json

### This is where simulation accuracy lives.
### Every agent spawned in this zone gets parameters from this file.

### Schema
{
  "zone_id": "DEL_SHAHDARA",
  "zone_name": "Shahdara",
  "city_id": "DEL",
  "state_id": "DL",

  "geography": {
    "centroid_lat": 28.6692,
    "centroid_lng": 77.2847,
    "area_sq_km": 57.8,
    "ward_ids": [201, 202, 203, 204, 205, 206, 207, 208],
      // Census 2011 ward numbers falling within this zone
    "geojson_path": "zones/DEL/geojson/DEL_SHAHDARA.geojson"
  },

  "demographics": {
    "population": 1710000,
    "population_density_per_sqkm": 29585,
    "average_household_size": 4.6,
    "literacy_rate": 0.83,
    "sc_st_population_share": 0.19,
    "data_source": "Census 2011 ward tables, Delhi"
  },

  "income_profile": {
    "distribution": {
      "decile_1": 0.14,
      "decile_2": 0.13,
      "decile_3": 0.12,
      "decile_4": 0.12,
      "decile_5": 0.11,
      "decile_6": 0.10,
      "decile_7": 0.09,
      "decile_8": 0.08,
      "decile_9": 0.07,
      "decile_10": 0.04
    },
      // Skewed left — Shahdara is predominantly lower-middle income
      // Source: NSSO 78th Round MPCE distribution, Delhi East district
    "median_monthly_income": 18500,
    "informal_employment_rate": 0.61,
    "primary_occupations": ["manufacturing", "trade",
                             "transport", "construction"],
    "data_source": "NSSO 78th Round + Census 2011 B-Series worker tables"
  },

  "commute_profile": {
    "primary_mode": "metro",
    "secondary_mode": "bus",
    "metro_dependency_score": 0.74,
      // 0-1. High = agents very sensitive to metro fare/service changes
    "avg_commute_distance_km": 11.2,
    "avg_commute_time_min": 42,
    "nearest_metro_lines": ["RED", "PINK"],
    "nearest_metro_stations": ["Shahdara", "Welcome", "Jaffrabad",
                                "Maujpur"],
    "car_ownership_rate": 0.18,
      // Low = high transit dependency = high fare sensitivity
    "data_source": "DMRC Origin-Destination Survey 2022,
                    Census 2011 Table D-13 (mode of travel to work)"
  },

  "sensitivity_parameters": {
    "fare_sensitivity_score": 0.84,
      // 0-1. How sharply agents respond to fare changes.
      // Derived from: income level, commute dependency, car ownership
      // Shahdara: HIGH (low income + high metro dependency)

    "examination_sensitivity_score": 0.71,
      // Relevance of examination policy scenarios to this zone
      // Driven by: student-age population share + coaching centre density

    "collective_action_threshold": 0.38,
      // Proportion of connected agents switching behaviour needed
      // to trigger organised resistance. Lower = easier to organise.
      // Source: union density + political contestation index from state

    "information_diffusion_speed": 0.72,
      // How fast decisions/news spread through zone's social network
      // WhatsApp penetration + literacy + digital access composite
      // Source: TRAI Digital India Report + IAMAI Internet Report

    "loss_aversion_coefficient": 0.81,
      // Zone-level override of state baseline
      // Lower income zones are more loss averse
      // Source: World Values Survey India + NSSO expenditure data

    "institutional_trust_railways": 0.54,
      // Trust in Indian Railways / Delhi Metro specifically
      // Source: Lokniti-CSDS 2024, disaggregated by income class

    "institutional_trust_examinations": 0.68,
      // Trust in NTA/CBSE examination boards
      // Source: Lokniti-CSDS 2024 + post-NEET 2024 survey data

    "political_mobilisation_index": 0.73
      // How politically activated this zone's population is
      // Source: 2024 Lok Sabha turnout + margin data (ECI)
  },

  "social_network_parameters": {
    "avg_connections_tier1": 41,
    "clustering_coefficient": 0.68,
      // High = tight community clusters (residential colony structure)
    "cross_income_bridge_frequency": 0.12,
      // Low = mostly within-income connections
      // Shahdara has low cross-income mixing
    "tier2_agent_density": 0.038,
      // Proportion of zone population that are Tier 2 agents
    "dominant_network_type": "residential_colony"
      // residential_colony | workplace | religious | mixed
  },

  "informal_economy_nodes": [
    {
      "node_id": "SHAHDARA_MARKET_1",
      "type": "street_market",
      "location": [28.6720, 77.2880],
      "daily_footfall": 12000,
      "transit_dependency": 0.71,
        // Share of footfall arriving by transit
      "employment_generated": 340
        // Informal jobs dependent on this node's footfall
    }
    // ... other market/commercial nodes in zone
  ],
    // These nodes activate when agent commute decisions
    // affect footfall — enabling informal economy cascade simulation

  "tier1_agent_archetype_weights": {
    "daily_commuter_worker": 0.41,
    "student": 0.18,
    "homemaker": 0.14,
    "self_employed_informal": 0.16,
    "government_employee": 0.06,
    "professional_formal": 0.05
  },
    // Controls what types of agents are generated from this zone
    // Weights must sum to 1.0
    // Each archetype has a base personality vector template
    // that zone parameters then modify

  "tier2_agent_types": {
    "local_journalist": 1,
    "rwa_president": 2,
    "union_representative": 3,
    "school_principal": 1,
    "small_business_owner": 8,
    "local_councillor": 1
  }
    // Exact Tier 2 agents spawned in this zone
    // These become the social influence hub nodes
}

---

## Complete Zone List — Phase 1

### Delhi (12 zones)
zones/DEL/DEL_CENTRAL.json      — Connaught Place, government offices
zones/DEL/DEL_NEWDELHI.json     — Lutyens zone, embassy area, high income
zones/DEL/DEL_NORTH.json        — Civil Lines, Kamla Nagar
zones/DEL/DEL_NORTHEAST.json    — Mustafabad, Seelampur (dense, low income)
zones/DEL/DEL_EAST.json         — Patparganj, Mayur Vihar
zones/DEL/DEL_SHAHDARA.json     — Shahdara (detailed above)
zones/DEL/DEL_SOUTH.json        — Saket, Malviya Nagar, mid-high income
zones/DEL/DEL_SOUTHWEST.json    — Dwarka, Janakpuri
zones/DEL/DEL_WEST.json         — Rajouri Garden, Punjabi Bagh
zones/DEL/DEL_NORTHWEST.json    — Rohini, Pitampura
zones/DEL/DEL_NCR_NOIDA.json    — Noida (UP state params, Delhi commute)
zones/DEL/DEL_NCR_GURGAON.json  — Gurugram (Haryana state, tech workers)

### Mumbai (11 zones)
zones/MUM/MUM_SOUTHMUMBAI.json  — Colaba, Fort, Nariman Point (high income)
zones/MUM/MUM_CENTRAL.json      — Dadar, Parel, Worli
zones/MUM/MUM_DHARAVI.json      — Dharavi (highest informal economy density)
zones/MUM/MUM_BANDRA.json       — Bandra, Khar (mid-high, mixed)
zones/MUM/MUM_ANDHERI.json      — Andheri, SEEPZ (commercial)
zones/MUM/MUM_BORIVALI.json     — Borivali, Dahisar (commuter belt)
zones/MUM/MUM_THANE.json        — Thane (satellite city)
zones/MUM/MUM_NAVI.json         — Navi Mumbai (planned city, distinct profile)
zones/MUM/MUM_KURLA.json        — Kurla, Vidyavihar (transit hub, dense)
zones/MUM/MUM_CHEMBUR.json      — Chembur, Govandi
zones/MUM/MUM_VASAI.json        — Vasai-Virar (far commuter belt)

### Bengaluru (9 zones)
zones/BLR/BLR_CENTRAL.json      — MG Road, Brigade Road
zones/BLR/BLR_WHITEFIELD.json   — IT corridor, high income
zones/BLR/BLR_ELECTRONIC_CITY.json — Tech park cluster
zones/BLR/BLR_NORTH.json        — Hebbal, Yelahanka
zones/BLR/BLR_SOUTH.json        — Jayanagar, JP Nagar
zones/BLR/BLR_EAST.json         — Indiranagar, Marathahalli
zones/BLR/BLR_WEST.json         — Rajajinagar, Malleshwaram
zones/BLR/BLR_OUTER_RING.json   — ORR corridor, new developments
zones/BLR/BLR_PERIURBAN.json    — Peri-urban fringe, low connectivity

### Chennai (8 zones)
zones/CHN/CHN_CENTRAL.json      — Egmore, Park Town
zones/CHN/CHN_NORTH.json        — Perambur, Kolathur
zones/CHN/CHN_SOUTH.json        — Adyar, Velachery
zones/CHN/CHN_WEST.json         — Anna Nagar, Kilpauk
zones/CHN/CHN_OMR.json          — IT corridor, high income
zones/CHN/CHN_TAMBARAM.json     — Southern commuter belt
zones/CHN/CHN_AMBATTUR.json     — Industrial zone, north-west
zones/CHN/CHN_PERIURBAN.json    — Peri-urban expansion zone

### Hyderabad (8 zones)
zones/HYD/HYD_CENTRAL.json      — Abids, Nampally
zones/HYD/HYD_HITECH.json       — HiTech City, Madhapur (tech cluster)
zones/HYD/HYD_OLDCITY.json      — Charminar, Falaknuma (distinct profile)
zones/HYD/HYD_SECUNDERABAD.json — Twin city, distinct transport dependency
zones/HYD/HYD_KUKATPALLY.json   — Dense residential, commuter zone
zones/HYD/HYD_KONDAPUR.json     — New residential, mid-high income
zones/HYD/HYD_LB_NAGAR.json     — South zone, mixed income
zones/HYD/HYD_PERIURBAN.json    — Growth corridor

### Kolkata (8 zones)
zones/KOL/KOL_CENTRAL.json      — BBD Bagh, Esplanade (CBD)
zones/KOL/KOL_NORTH.json        — Shyambazar, Shobhabazar
zones/KOL/KOL_SOUTH.json        — Ballygunge, Alipore (high income)
zones/KOL/KOL_EAST.json         — Salt Lake, Rajarhat (IT corridor)
zones/KOL/KOL_HOWRAH.json       — Howrah (industrial, river crossing)
zones/KOL/KOL_JADAVPUR.json     — University zone, educated workforce
zones/KOL/KOL_TRAM_CORRIDOR.json — Unique: tram network zone (no other city)
zones/KOL/KOL_PERIURBAN.json    — North 24 Parganas fringe

Total zones Phase 1: 56 zones across 6 cities

---

## Agent Factory — How Zone Config Is Read

### Agent generation flow per zone:

1. AgentFactory.load_zone(zone_id)
   → reads zones/[city]/[zone_id].json
   → validates all required fields
   → resolves parent city config (cities/[city_id].json)
   → resolves parent state config (states/[state_id].json)
   → builds merged ZoneContext object (zone overrides city, city overrides state)

2. AgentFactory.spawn_agents(zone_context, n_agents)
   → determines archetype distribution from tier1_agent_archetype_weights
   → for each archetype slot:
       - loads archetype base template
       - applies zone-level parameter overrides
       - samples from zone income distribution
       - assigns commute route based on zone transport profile
       - assigns social connections based on zone network parameters
       - seeds 90-day memory with zone-specific recent event history
   → returns List[Tier1Agent]

3. AgentFactory.spawn_tier2_agents(zone_context)
   → reads tier2_agent_types from zone config
   → spawns exactly the specified Tier 2 agents
   → assigns them as hub nodes in zone's social network
   → returns List[Tier2Agent]

### Parameter Resolution (Zone overrides City overrides State)

If a parameter exists in zone config: use zone value
If not in zone config but in city config: use city value
If not in city config but in state config: use state value
If not in state config: use national default from defaults.json

This means:
- Shahdara agents inherit Delhi's DMRC transport network (city level)
- But use Shahdara's income distribution (zone level)
- And use Delhi NCT's union legal framework (state level)
- And fall back to national loss aversion default if zone doesn't specify

### national defaults.json (fallback values)
{
  "loss_aversion_coefficient": 0.74,
  "information_diffusion_speed": 0.61,
  "collective_action_threshold": 0.45,
  "institutional_trust_railways": 0.58,
  "institutional_trust_examinations": 0.65,
  "political_mobilisation_index": 0.52,
  "informal_employment_rate": 0.47,
  "avg_connections_tier1": 35,
  "clustering_coefficient": 0.58
}

---

## Why This Structure Matters for Simulation Accuracy

The Dharavi simulation is different from the Bandra simulation because:
★ Dharavi zone: informal_employment_rate 0.71, median income ₹11,200,
  fare_sensitivity_score 0.91, 14 informal_economy_nodes
★ Bandra West zone: informal_employment_rate 0.22, median income ₹68,000,
  fare_sensitivity_score 0.31, 2 informal_economy_nodes

A 20% fare hike hits these two zones differently in ways that
any Mumbaikar would recognise as accurate. That recognition is what
makes a judge — especially one familiar with Mumbai — trust the platform.

The same policy. Two completely different simulation outcomes.
That is the point of the zone architecture.