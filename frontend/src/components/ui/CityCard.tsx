import React from 'react';
import { DataChip } from './DataChip';

interface CityCardProps {
  name: string;
  description: string;
  population: string;
  threatLevel: 'LOW' | 'ELEVATED' | 'CRITICAL';
  status: 'SECURE' | 'MONITORING' | 'COMPROMISED' | 'DORMANT';
  onClick?: () => void;
  isActive?: boolean;
  className?: string;
}

const statusToVariant: Record<string, 'secure' | 'monitoring' | 'compromised' | 'dormant'> = {
  SECURE: 'secure',
  MONITORING: 'monitoring',
  COMPROMISED: 'compromised',
  DORMANT: 'dormant',
};

const threatColorMap: Record<string, string> = {
  LOW: 'var(--color-success)',
  ELEVATED: 'var(--color-warn)',
  CRITICAL: 'var(--color-alert)',
};

export const CityCard: React.FC<CityCardProps> = ({
  name,
  description,
  population,
  threatLevel,
  status,
  onClick,
  isActive = false,
  className = '',
}) => {
  const isCompromised = status === 'COMPROMISED';

  return (
    <div
      className={`glass-panel glow-hover ${className}`}
      onClick={onClick}
      style={{
        cursor: 'crosshair',
        borderColor: isCompromised
          ? 'var(--color-alert-border)'
          : isActive
          ? 'var(--color-primary)'
          : undefined,
        borderLeft: isActive || isCompromised
          ? `3px solid ${isCompromised ? 'var(--color-alert)' : 'var(--color-primary)'}`
          : undefined,
        ...(isActive && !isCompromised
          ? { boxShadow: '0 0 8px rgba(0, 229, 255, 0.3), 0 0 2px rgba(0, 229, 255, 0.6)' }
          : {}),
        ...(isCompromised
          ? { boxShadow: '0 0 8px rgba(255, 0, 85, 0.3), 0 0 2px rgba(255, 0, 85, 0.6)' }
          : {}),
        transition: 'border-color 150ms ease-out, box-shadow 150ms ease-out',
        padding: 16,
      }}
    >
      {/* Top: name + status chip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 24,
            fontWeight: 400,
            color: isCompromised ? 'var(--color-alert)' : 'var(--color-text-primary)',
          }}
        >
          {name}
        </span>
        <DataChip label={status} variant={statusToVariant[status] || 'dormant'} />
      </div>

      {/* Description */}
      <div
        style={{
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          color: 'var(--color-text-secondary)',
          lineHeight: 1.6,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical' as const,
          overflow: 'hidden',
          marginBottom: 12,
        }}
      >
        {description}
      </div>

      {/* Divider */}
      <div style={{ borderTop: '1px solid var(--color-border-dim)', marginBottom: 12 }} />

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <div
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 10,
              letterSpacing: '0.1em',
              color: 'var(--color-text-dim)',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            POPULATION
          </div>
          <div
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 14,
              color: 'var(--color-text-primary)',
            }}
          >
            {population}
          </div>
        </div>
        <div>
          <div
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 10,
              letterSpacing: '0.1em',
              color: 'var(--color-text-dim)',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            THREAT_LVL
          </div>
          <div
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 14,
              color: threatColorMap[threatLevel],
            }}
          >
            {threatLevel}
          </div>
        </div>
      </div>
    </div>
  );
};
