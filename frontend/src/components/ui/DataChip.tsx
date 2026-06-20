import React from 'react';

type ChipVariant =
  | 'online' | 'stable'
  | 'warn' | 'monitoring' | 'elevated'
  | 'critical' | 'compromised'
  | 'dormant'
  | 'secure';

interface DataChipProps {
  label: string;
  variant: ChipVariant;
  icon?: string;
  className?: string;
  large?: boolean;
}

const variantStyles: Record<ChipVariant, { borderColor: string; color: string; bg?: string }> = {
  online:      { borderColor: 'var(--color-success)', color: 'var(--color-success)' },
  stable:      { borderColor: 'var(--color-success)', color: 'var(--color-success)' },
  warn:        { borderColor: 'var(--color-warn)', color: 'var(--color-warn)' },
  monitoring:  { borderColor: 'var(--color-warn)', color: 'var(--color-warn)' },
  elevated:    { borderColor: 'var(--color-warn)', color: 'var(--color-warn)', bg: 'var(--color-warn-dim)' },
  critical:    { borderColor: 'var(--color-alert)', color: 'var(--color-alert)', bg: 'var(--color-alert-dim)' },
  compromised: { borderColor: 'var(--color-alert)', color: 'var(--color-alert)', bg: 'var(--color-alert-dim)' },
  dormant:     { borderColor: 'var(--color-text-ghost)', color: 'var(--color-text-ghost)' },
  secure:      { borderColor: 'var(--color-primary)', color: 'var(--color-primary)' },
};

export const DataChip: React.FC<DataChipProps> = ({ label, variant, icon, className = '', large = false }) => {
  const style = variantStyles[variant];
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: large ? 'center' : undefined,
        gap: 4,
        padding: large ? '8px 12px' : '4px 8px',
        border: `1px solid ${style.borderColor}`,
        background: style.bg || 'transparent',
        fontFamily: 'var(--font-data)',
        fontSize: large ? 12 : 10,
        letterSpacing: '0.1em',
        color: style.color,
        textTransform: 'uppercase' as const,
        lineHeight: 1,
        whiteSpace: 'nowrap' as const,
        width: large ? '100%' : undefined,
        height: large ? 44 : undefined,
      }}
    >
      {icon && <span>{icon}</span>}
      [{label}]
    </span>
  );
};
