export interface DivergenceItem {
  label: string;
  actual: number;
  predicted: number;
  delta: number;
}

export interface RoadmapPhase {
  label: string;
  status: 'complete' | 'active' | 'pending';
  date: string;
}

export interface MethodologyItem {
  icon: string;
  title: string;
  description: string;
}

export const hindcastData = {
  globalAccuracy: 94.2,
  mse: 0.08,
  populationAnalyzed: 14200000,
  divergenceMatrix: [
    { label: 'URBAN_DENSITY_1990', actual: 72, predicted: 68, delta: 4.0 },
    { label: 'RESOURCE_ALLOC_1995', actual: 58, predicted: 60, delta: -2.0 },
    { label: 'MIGRATION_VECTORS_2000', actual: 85, predicted: 82, delta: 3.0 },
    { label: 'INFRASTRUCTURE_DECAY_', actual: 41, predicted: 44, delta: -3.0 },
  ] as DivergenceItem[],
  roadmap: [
    { label: 'DATA_INGEST', status: 'complete', date: '2024.01' },
    { label: 'MODEL_TRAIN', status: 'complete', date: '2024.06' },
    { label: 'VALIDATION', status: 'active', date: '2024.09' },
    { label: 'DEPLOYMENT', status: 'pending', date: '2025.01' },
  ] as RoadmapPhase[],
  methodology: {
    description:
      "The hindcast procedure forces the primary synthesis engine to predict known historical states spanning 1990–2010. By restricting contemporary data injections, we isolate the core algorithm's generative accuracy.",
    items: [
      {
        icon: '✳',
        title: 'Data Sanitization',
        description: 'All post-2010 records are hard-purged from the validation matrix prior to model initialization.',
      },
      {
        icon: '⚖',
        title: 'Parameter Weighting',
        description: 'Socio-economic variables are heavily weighted against empirical census tracts.',
      },
      {
        icon: '▦',
        title: 'Variance Tolerance',
        description: 'Acceptable deviation is strictly maintained within a 0.15 MSE threshold across all sectors.',
      },
    ] as MethodologyItem[],
  },
};
