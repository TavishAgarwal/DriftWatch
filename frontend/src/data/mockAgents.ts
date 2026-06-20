export type LogType = 'EXEC' | 'WARN' | 'INFO';
export type Archetype = 'WORKER' | 'VENDOR' | 'STUDENT' | 'MIGRANT' | 'RETIRED' | 'TECH' | 'OFFICIAL';

export interface DecisionEntry {
  id: string;
  timestamp: string;
  archetype: Archetype;
  zone: string;
  decision: string;
  type: LogType;
}

export interface TelemetryEntry {
  id: string;
  timestamp: string;
  message: string;
  isAlert: boolean;
}

const decisions: Array<{ decision: string; type: LogType; archetype: Archetype }> = [
  { decision: 'ASSET REALLOCATION: SECTOR 7G. YIELD PROJECTION +12%.', type: 'EXEC', archetype: 'OFFICIAL' },
  { decision: 'ANOMALY DETECTED IN DATALINK BETA. PACKET LOSS 4.2%.', type: 'WARN', archetype: 'TECH' },
  { decision: 'SYNTHESIS ROUTINE COMPLETED. 4096 NODES UPDATED.', type: 'INFO', archetype: 'TECH' },
  { decision: 'MIGRATION VECTOR RECALCULATED. NODE_DELTA +0.8%.', type: 'EXEC', archetype: 'MIGRANT' },
  { decision: 'THERMAL VARIANCE EXCEEDS THRESHOLD. COOLING PROTOCOL INITIATED.', type: 'WARN', archetype: 'WORKER' },
  { decision: 'MARKET SENTIMENT ANALYST DEPLOYED TO NODE 42.', type: 'INFO', archetype: 'VENDOR' },
  { decision: 'POPULATION FLUX STABILIZED IN SECTOR_12. DELTA -0.02%.', type: 'INFO', archetype: 'OFFICIAL' },
  { decision: 'RESOURCE DISTRIBUTION MATRIX UPDATED. 1024 AGENTS REASSIGNED.', type: 'EXEC', archetype: 'OFFICIAL' },
  { decision: 'ANOMALY_LOGGED: SECTOR_7G. UNAUTHORIZED ACCESS ATTEMPT.', type: 'WARN', archetype: 'TECH' },
  { decision: 'TRANSIT ROUTING OPTIMIZED. EFFICIENCY +3.4%.', type: 'EXEC', archetype: 'WORKER' },
  { decision: 'STUDENT ENROLLMENT SURGE DETECTED IN NODE_DELHI_09.', type: 'INFO', archetype: 'STUDENT' },
  { decision: 'VENDOR NETWORK DISRUPTION. SUPPLY CHAIN REROUTING...', type: 'WARN', archetype: 'VENDOR' },
  { decision: 'RETIREMENT BENEFIT RECALCULATION COMPLETE. 2048 RECORDS.', type: 'INFO', archetype: 'RETIRED' },
  { decision: 'SURVEILLANCE GRID RECALIBRATING. ETA 00:04:32.', type: 'INFO', archetype: 'TECH' },
  { decision: 'POWER GRID STRESS TEST INITIATED. LOAD AT 94%.', type: 'EXEC', archetype: 'WORKER' },
  { decision: 'DATA INTEGRITY CHECK FAILED ON NODE_MUM_04. RETRYING...', type: 'WARN', archetype: 'TECH' },
  { decision: 'ECONOMIC MODEL CONVERGENCE ACHIEVED. MSE: 0.04.', type: 'EXEC', archetype: 'OFFICIAL' },
  { decision: 'MIGRANT FLOW PATTERN ANOMALY. CLUSTER ANALYSIS RUNNING.', type: 'WARN', archetype: 'MIGRANT' },
  { decision: 'INFRASTRUCTURE DECAY INDEX UPDATED. SECTOR_3: -2.1%.', type: 'INFO', archetype: 'WORKER' },
  { decision: 'NEURAL PATHWAY OPTIMIZATION COMPLETE. LATENCY -12MS.', type: 'EXEC', archetype: 'TECH' },
  { decision: 'FISCAL POLICY SIMULATION BATCH 0x7F PROCESSED.', type: 'INFO', archetype: 'OFFICIAL' },
  { decision: 'WATER TABLE SENSOR ARRAY OFFLINE IN SECTOR_5.', type: 'WARN', archetype: 'WORKER' },
  { decision: 'EDUCATION SUBSIDY MODEL VALIDATED. ACCURACY 96.1%.', type: 'EXEC', archetype: 'STUDENT' },
  { decision: 'VENDOR REGISTRATION SPIKE: +340 IN LAST CYCLE.', type: 'INFO', archetype: 'VENDOR' },
  { decision: 'PENSION FUND ALLOCATION RECALIBRATED. YIELD +1.8%.', type: 'EXEC', archetype: 'RETIRED' },
  { decision: 'BANDWIDTH SATURATION IN NODE_BLR_11. THROTTLING ACTIVE.', type: 'WARN', archetype: 'TECH' },
  { decision: 'DEMOGRAPHIC SHIFT DETECTED. URBAN DENSITY +0.6%.', type: 'INFO', archetype: 'MIGRANT' },
  { decision: 'GRID STABILITY AT 97.2%. ALL SECTORS NOMINAL.', type: 'INFO', archetype: 'WORKER' },
  { decision: 'TRADE ROUTE ANALYSIS COMPLETE. 6 NEW VECTORS IDENTIFIED.', type: 'EXEC', archetype: 'VENDOR' },
  { decision: 'SECURITY PROTOCOL ALPHA ENGAGED. PERIMETER SECURED.', type: 'EXEC', archetype: 'OFFICIAL' },
  { decision: 'STUDENT PERFORMANCE METRICS AGGREGATED. N=45,000.', type: 'INFO', archetype: 'STUDENT' },
  { decision: 'COOLING SYSTEM FAILURE IN SECTOR_8. BACKUP ENGAGED.', type: 'WARN', archetype: 'WORKER' },
  { decision: 'PREDICTIVE MODEL ACCURACY BENCHMARK: 94.2%.', type: 'INFO', archetype: 'TECH' },
  { decision: 'LABOR MARKET EQUILIBRIUM ANALYSIS. DEFICIT: 2.4%.', type: 'EXEC', archetype: 'WORKER' },
  { decision: 'SATELLITE UPLINK RESTORED. LATENCY WITHIN TOLERANCE.', type: 'INFO', archetype: 'TECH' },
  { decision: 'POPULATION CENSUS SYNC COMPLETED. DELTA: +12,042.', type: 'EXEC', archetype: 'OFFICIAL' },
  { decision: 'MIGRANT HOUSING ALLOCATION UPDATED. 512 UNITS ASSIGNED.', type: 'EXEC', archetype: 'MIGRANT' },
  { decision: 'ANOMALY IN FINANCIAL SUBSYSTEM. AUDIT TRIGGERED.', type: 'WARN', archetype: 'VENDOR' },
  { decision: 'HEALTHCARE NODE CAPACITY AT 78%. MONITORING.', type: 'INFO', archetype: 'RETIRED' },
  { decision: 'TRANSPORT NETWORK LOAD BALANCED. EFFICIENCY: 91%.', type: 'EXEC', archetype: 'WORKER' },
  { decision: 'ENCRYPTION KEY ROTATION COMPLETE. CYCLE 0xAF.', type: 'INFO', archetype: 'TECH' },
  { decision: 'FOOD DISTRIBUTION NETWORK OPTIMIZED. WASTE -8.3%.', type: 'EXEC', archetype: 'VENDOR' },
  { decision: 'SCHOLARSHIP DATABASE SYNC. 1,024 RECORDS UPDATED.', type: 'INFO', archetype: 'STUDENT' },
  { decision: 'EMERGENCY PROTOCOL STANDBY. THREAT LEVEL: ELEVATED.', type: 'WARN', archetype: 'OFFICIAL' },
  { decision: 'RESIDENTIAL POWER CONSUMPTION SPIKE. SECTOR_9: +14%.', type: 'WARN', archetype: 'WORKER' },
  { decision: 'CLIMATE MODEL INTEGRATION COMPLETE. 8 VARIABLES ADDED.', type: 'EXEC', archetype: 'TECH' },
  { decision: 'RETIREMENT FACILITY OCCUPANCY: 82%. STABLE.', type: 'INFO', archetype: 'RETIRED' },
  { decision: 'CROSS-BORDER DATA FLOW ANALYSIS. THROUGHPUT: 4.2TB/S.', type: 'INFO', archetype: 'TECH' },
  { decision: 'AGRICULTURAL YIELD PREDICTION UPDATED. +6% FORECAST.', type: 'EXEC', archetype: 'VENDOR' },
  { decision: 'PUBLIC TRANSIT RIDERSHIP ANOMALY. -12% VS BASELINE.', type: 'WARN', archetype: 'MIGRANT' },
];

const zones = ['SECTOR_1', 'SECTOR_3', 'SECTOR_5', 'SECTOR_7G', 'SECTOR_8', 'SECTOR_9', 'SECTOR_12', 'SECTOR_14'];

function formatTime(h: number, m: number, s: number): string {
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function generateDecisionFeed(): DecisionEntry[] {
  let h = 14, m = 2, s = 44;
  return decisions.map((d, i) => {
    s -= Math.floor(Math.random() * 15) + 5;
    if (s < 0) { s += 60; m--; }
    if (m < 0) { m += 60; h--; }
    return {
      id: `dec-${i}`,
      timestamp: formatTime(h, m, Math.max(0, s)),
      archetype: d.archetype,
      zone: zones[Math.floor(Math.random() * zones.length)],
      decision: d.decision,
      type: d.type,
    };
  });
}

const telemetryMessages = [
  { message: 'NODE_DELHI_09 CONNECTED', isAlert: false },
  { message: 'POPULATION_FLUX DETECTED (+0.04%)', isAlert: false },
  { message: 'SURVEILLANCE_GRID RECALIBRATING...', isAlert: false },
  { message: 'ANOMALY_LOGGED: SECTOR_7G', isAlert: true },
  { message: 'BANDWIDTH ALLOCATION OPTIMIZED', isAlert: false },
  { message: 'NODE_MUMBAI_04 HEARTBEAT OK', isAlert: false },
  { message: 'ENCRYPTION LAYER ROTATED', isAlert: false },
  { message: 'THERMAL SENSOR ARRAY CALIBRATED', isAlert: false },
  { message: 'DATA_PIPELINE THROUGHPUT: 2.4GB/S', isAlert: false },
  { message: 'ANOMALY_DETECTED: SUBSYSTEM_ALPHA', isAlert: true },
  { message: 'LOAD BALANCER REDISTRIBUTING...', isAlert: false },
  { message: 'NODE_KOLKATA_02 PACKET LOSS: 0.8%', isAlert: false },
  { message: 'SATELLITE_UPLINK ESTABLISHED', isAlert: false },
  { message: 'CENSUS_SYNC DELTA: +4,201', isAlert: false },
  { message: 'WARNING: MEMORY THRESHOLD 85%', isAlert: true },
  { message: 'FIREWALL RULES UPDATED: 48 ENTRIES', isAlert: false },
  { message: 'GRID_MONITOR HEARTBEAT NOMINAL', isAlert: false },
  { message: 'RESOURCE_VECTOR RECALCULATED', isAlert: false },
  { message: 'ANOMALY_LOGGED: FINANCIAL_SUBSYSTEM', isAlert: true },
  { message: 'COMPRESSION_RATIO OPTIMIZED: 4.2:1', isAlert: false },
];

export function generateTelemetryFeed(): TelemetryEntry[] {
  let h = 14, m = 2, s = 1;
  return telemetryMessages.map((t, i) => {
    const entry = {
      id: `tel-${i}`,
      timestamp: formatTime(h, m, s),
      message: t.message,
      isAlert: t.isAlert,
    };
    s += Math.floor(Math.random() * 8) + 2;
    if (s >= 60) { s -= 60; m++; }
    if (m >= 60) { m -= 60; h++; }
    return entry;
  });
}
