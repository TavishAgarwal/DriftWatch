import React from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  type: 'EXEC' | 'WARN' | 'INFO';
  decision: string;
}

interface TerminalLogProps {
  entries: LogEntry[];
  maxHeight?: number | string;
  className?: string;
}

const badgeColors: Record<string, { border: string; color: string }> = {
  EXEC: { border: 'var(--color-primary)', color: 'var(--color-primary)' },
  WARN: { border: 'var(--color-warn)', color: 'var(--color-warn)' },
  INFO: { border: 'var(--color-text-secondary)', color: 'var(--color-text-secondary)' },
};

function getMessageColor(type: string, message: string): string {
  if (message.includes('ANOMALY') || message.includes('ERROR')) {
    return 'var(--color-alert)';
  }
  switch (type) {
    case 'EXEC': return 'var(--color-primary)';
    case 'WARN': return 'var(--color-warn)';
    default: return 'var(--color-text-secondary)';
  }
}

export const TerminalLog: React.FC<TerminalLogProps> = ({
  entries,
  maxHeight = 400,
  className = '',
}) => {
  return (
    <div
      className={className}
      style={{
        maxHeight,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {entries.map((entry) => {
        const badge = badgeColors[entry.type] || badgeColors.INFO;
        return (
          <div
            key={entry.id}
            className="terminal-entry"
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              fontFamily: 'var(--font-data)',
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <span style={{ color: 'var(--color-text-dim)', flexShrink: 0, whiteSpace: 'nowrap' }}>
              {entry.timestamp}
            </span>
            <span
              style={{
                border: `1px solid ${badge.border}`,
                color: badge.color,
                padding: '2px 6px',
                fontSize: 10,
                flexShrink: 0,
                letterSpacing: '0.05em',
                lineHeight: 1,
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              {entry.type}
            </span>
            <span style={{ color: getMessageColor(entry.type, entry.decision) }}>
              {entry.decision}
            </span>
          </div>
        );
      })}
    </div>
  );
};
