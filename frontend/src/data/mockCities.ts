export interface City {
  id: string;
  name: string;
  population: number;
  populationDisplay: string;
  threatLevel: 'LOW' | 'ELEVATED' | 'CRITICAL';
  status: 'SECURE' | 'MONITORING' | 'COMPROMISED' | 'DORMANT';
  confidence: 'A' | 'B' | 'C';
  coordinates: { lat: number; lng: number };
  zones: string[];
  description: string;
  dailyRidership: number;
}

export const cities: City[] = [
  {
    id: 'DEL-09',
    name: 'Delhi',
    population: 32941000,
    populationDisplay: '32.9M',
    threatLevel: 'LOW',
    status: 'SECURE',
    confidence: 'A',
    coordinates: { lat: 28.7041, lng: 77.1025 },
    zones: ['SECTOR_9', 'SECTOR_12', 'SECTOR_7G'],
    description: 'Primary administrative hub. Grid stability at 97.2%. Infrastructure matrix fully operational.',
    dailyRidership: 6200000,
  },
  {
    id: 'MUM-04',
    name: 'Mumbai',
    population: 21297000,
    populationDisplay: '21.3M',
    threatLevel: 'ELEVATED',
    status: 'MONITORING',
    confidence: 'B',
    coordinates: { lat: 19.0760, lng: 72.8777 },
    zones: ['SECTOR_3', 'SECTOR_8'],
    description: 'Financial nexus experiencing elevated network fluctuations. Maintenance protocols active.',
    dailyRidership: 7500000,
  },
  {
    id: 'BLR-11',
    name: 'Bengaluru',
    population: 13193000,
    populationDisplay: '13.2M',
    threatLevel: 'LOW',
    status: 'SECURE',
    confidence: 'A',
    coordinates: { lat: 12.9716, lng: 77.5946 },
    zones: ['SECTOR_5', 'SECTOR_14'],
    description: 'Technology corridor. Neural network integration at 94.8%. Surveillance matrix nominal.',
    dailyRidership: 4200000,
  },
  {
    id: 'CHN-06',
    name: 'Chennai',
    population: 11235000,
    populationDisplay: '11.2M',
    threatLevel: 'ELEVATED',
    status: 'MONITORING',
    confidence: 'B',
    coordinates: { lat: 13.0827, lng: 80.2707 },
    zones: ['SECTOR_2', 'SECTOR_11'],
    description: 'Coastal defense grid active. Tidal variance algorithms compensating within tolerance.',
    dailyRidership: 3800000,
  },
  {
    id: 'HYD-15',
    name: 'Hyderabad',
    population: 10534000,
    populationDisplay: '10.5M',
    threatLevel: 'LOW',
    status: 'SECURE',
    confidence: 'A',
    coordinates: { lat: 17.3850, lng: 78.4867 },
    zones: ['SECTOR_6', 'SECTOR_10'],
    description: 'Dual-core processing hub. Pharmaceutical synthesis routines operating at peak capacity.',
    dailyRidership: 3200000,
  },
  {
    id: 'KOL-02',
    name: 'Kolkata',
    population: 15134000,
    populationDisplay: '15.1M',
    threatLevel: 'CRITICAL',
    status: 'COMPROMISED',
    confidence: 'C',
    coordinates: { lat: 22.5726, lng: 88.3639 },
    zones: ['SECTOR_1', 'SECTOR_4', 'SECTOR_7'],
    description: 'Massive data breach detected in central banking node. Connection severely degraded.',
    dailyRidership: 5100000,
  },
];

export const geoSynthNodes: City[] = [
  {
    id: 'DEL-09',
    name: 'Delhi',
    population: 32941000,
    populationDisplay: '32.9M',
    threatLevel: 'LOW',
    status: 'SECURE',
    confidence: 'A',
    coordinates: { lat: 28.7041, lng: 77.1025 },
    zones: ['SECTOR_9', 'SECTOR_12', 'SECTOR_7G'],
    description: 'Primary administrative hub. Grid stability at 97.2%. Surveillance matrix fully integrated.',
    dailyRidership: 6200000,
  },
  {
    id: 'MUM-04',
    name: 'Mumbai',
    population: 21297000,
    populationDisplay: '21.3M',
    threatLevel: 'ELEVATED',
    status: 'MONITORING',
    confidence: 'B',
    coordinates: { lat: 19.0760, lng: 72.8777 },
    zones: ['SECTOR_3', 'SECTOR_8'],
    description: 'Financial nexus experiencing minor localized network fluctuations. Maintenance crews dispatched.',
    dailyRidership: 7500000,
  },
  {
    id: 'KOL-02',
    name: 'Kolkata',
    population: 15134000,
    populationDisplay: '15.1M',
    threatLevel: 'CRITICAL',
    status: 'COMPROMISED',
    confidence: 'C',
    coordinates: { lat: 22.5726, lng: 88.3639 },
    zones: ['SECTOR_1', 'SECTOR_4', 'SECTOR_7'],
    description: 'Massive data breach detected in central banking node. Connection severely degraded.',
    dailyRidership: 5100000,
  },
];

