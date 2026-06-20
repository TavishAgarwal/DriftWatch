import React from 'react';
import { useCountUp } from '../../hooks/useCountUp';
import { SegmentBar } from './SegmentBar';

interface MetricCardProps {
  label: string;
  value: number;
  unit?: string;
  delta?: string;
  variant?: 'primary' | 'warn' | 'alert' | 'default';
  decimals?: number;
  showBar?: boolean;
  barValue?: number;
  className?: string;
  children?: React.ReactNode;
  large?: boolean;
}

const variantColorMap = {
  primary: 'var(--color-primary)',
  warn: 'var(--color-warn)',
  alert: 'var(--color-alert)',
  default: 'var(--color-text-primary)',
};

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  delta,
  variant = 'default',
  decimals = 0,
  showBar = false,
  barValue,
  className = '',
  children,
  large = true,
}) => {
  const animatedValue = useCountUp(value, 1200, decimals);
  const color = variantColorMap[variant];

  return (
    <div
      className={`glass-panel ${className}`}
      style={{ overflow: 'hidden', padding: 16 }}
    >
      <div
        style={{
          fontFamily: 'var(--font-data)',
          fontSize: 10,
          letterSpacing: '0.1em',
          color: 'var(--color-text-dim)',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}
      >
        {label}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: large ? 48 : 32,
            color,
            lineHeight: 1,
          }}
        >
          {decimals > 0 ? animatedValue.toFixed(decimals) : animatedValue.toLocaleString()}
        </span>
        {unit && (
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 14,
              color: 'var(--color-text-secondary)',
            }}
          >
            {unit}
          </span>
        )}
      </div>

      {delta && (
        <div
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 12,
            color: delta.startsWith('+') ? 'var(--color-success)' : delta.startsWith('-') ? 'var(--color-alert)' : 'var(--color-text-dim)',
            marginTop: 4,
          }}
        >
          {delta}
        </div>
      )}

      {children}

      {showBar && barValue !== undefined && (
        <div style={{ marginTop: 12 }}>
          <SegmentBar
            value={barValue}
            variant={variant === 'alert' ? 'alert' : variant === 'warn' ? 'warn' : 'primary'}
          />
        </div>
      )}
    </div>
  );
};
