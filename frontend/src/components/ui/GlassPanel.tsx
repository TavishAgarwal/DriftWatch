import React from 'react';

interface GlassPanelProps {
  title?: string;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  variant?: 'serif' | 'mono';
}

export const GlassPanel: React.FC<GlassPanelProps> = ({
  title,
  headerRight,
  children,
  className = '',
  variant = 'mono',
}) => {
  return (
    <div
      className={`glass-panel ${className}`}
      style={{ overflow: 'hidden' }}
    >
      {title && (
        <div
          style={{
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 12px',
            borderBottom: '1px solid var(--color-border-dim)',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontFamily: variant === 'serif' ? 'var(--font-display)' : 'var(--font-data)',
              fontSize: variant === 'serif' ? 18 : 12,
              fontWeight: 400,
              ...(variant === 'mono'
                ? {
                    textTransform: 'uppercase' as const,
                    letterSpacing: '0.1em',
                    color: 'var(--color-text-secondary)',
                  }
                : { color: 'var(--color-text-primary)' }),
            }}
          >
            {title}
          </span>
          {headerRight && <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{headerRight}</div>}
        </div>
      )}
      <div style={{ padding: 12 }}>{children}</div>
    </div>
  );
};
