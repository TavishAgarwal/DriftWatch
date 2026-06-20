import React, { useState, useEffect } from 'react';

interface ExecuteButtonProps {
  label: string;
  icon?: React.ReactNode;
  onClick?: () => void;
  loading?: boolean;
  className?: string;
}

const spinnerChars = ['◐', '◓', '◑', '◒'];

export const ExecuteButton: React.FC<ExecuteButtonProps> = ({
  label,
  icon,
  onClick,
  loading = false,
  className = '',
}) => {
  const [spinnerIdx, setSpinnerIdx] = useState(0);
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setSpinnerIdx(prev => (prev + 1) % spinnerChars.length);
    }, 200);
    return () => clearInterval(interval);
  }, [loading]);

  return (
    <button
      className={className}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      disabled={loading}
      style={{
        width: '100%',
        height: 56,
        background: hovered ? 'var(--color-primary-glow)' : 'var(--color-surface-container)',
        border: `1px solid ${hovered || loading ? 'var(--color-primary)' : 'var(--color-border)'}`,
        color: 'var(--color-text-primary)',
        fontFamily: 'var(--font-data)',
        fontSize: 14,
        letterSpacing: '0.1em',
        textTransform: 'uppercase' as const,
        cursor: 'crosshair',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        clipPath:
          'polygon(8px 0%, 100% 0%, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0% 100%, 0% 8px)',
        transition: 'background 150ms ease-out, border-color 150ms ease-out, box-shadow 150ms ease-out',
        ...(loading || hovered
          ? {
              boxShadow: '0 0 8px rgba(0, 229, 255, 0.3), 0 0 2px rgba(0, 229, 255, 0.6)',
            }
          : {}),
        outline: 'none',
      }}
    >
      {loading ? (
        <>
          <span style={{ fontSize: 18 }}>{spinnerChars[spinnerIdx]}</span>
          <span>EXECUTING...</span>
          <span className="cursor-blink" style={{ color: 'var(--color-primary)' }}>█</span>
        </>
      ) : (
        <>
          {icon && <span style={{ fontSize: 18, display: 'flex', alignItems: 'center' }}>{icon}</span>}
          <span>{label}</span>
        </>
      )}
    </button>
  );
};
