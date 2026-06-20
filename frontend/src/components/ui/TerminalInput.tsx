import React, { useState, useRef } from 'react';

interface TerminalInputProps {
  value?: string;
  onChange?: (val: string) => void;
  placeholder?: string;
  multiline?: boolean;
  rows?: number;
  className?: string;
  onSubmit?: (val: string) => void;
}

export const TerminalInput: React.FC<TerminalInputProps> = ({
  value: controlledValue,
  onChange,
  placeholder = '',
  multiline = false,
  rows = 1,
  className = '',
  onSubmit,
}) => {
  const [internalValue, setInternalValue] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const val = controlledValue !== undefined ? controlledValue : internalValue;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const newVal = e.target.value;
    if (onChange) onChange(newVal);
    else setInternalValue(newVal);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !multiline && onSubmit) {
      e.preventDefault();
      onSubmit(val);
      if (!controlledValue) setInternalValue('');
    }
  };

  const containerStyle: React.CSSProperties = {
    background: 'transparent',
    border: `1px solid ${focused ? 'var(--color-primary)' : 'var(--color-border)'}`,
    padding: 12,
    display: 'flex',
    alignItems: multiline ? 'flex-start' : 'center',
    gap: 8,
    cursor: 'text',
    transition: 'border-color 150ms ease-out, box-shadow 150ms ease-out',
    ...(focused
      ? {
          boxShadow: '0 0 8px rgba(0, 229, 255, 0.3), 0 0 2px rgba(0, 229, 255, 0.6)',
        }
      : {}),
  };

  const inputStyle: React.CSSProperties = {
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: 'var(--color-primary)',
    fontFamily: 'var(--font-data)',
    fontSize: 14,
    lineHeight: 1.4,
    flex: 1,
    resize: 'none',
    cursor: 'text',
    width: '100%',
  };

  return (
    <div
      className={className}
      style={containerStyle}
      onClick={() => inputRef.current?.focus()}
    >
      <span
        style={{
          color: 'var(--color-primary)',
          fontFamily: 'var(--font-data)',
          fontSize: 14,
          flexShrink: 0,
          lineHeight: 1.4,
        }}
      >
        &gt;
      </span>
      {multiline ? (
        <textarea
          ref={inputRef as React.RefObject<HTMLTextAreaElement>}
          value={val}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          rows={rows}
          style={{
            ...inputStyle,
            minHeight: rows * 22,
          }}
        />
      ) : (
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={val}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          style={inputStyle}
        />
      )}
      <span
        style={{
          color: 'var(--color-primary)',
          fontFamily: 'var(--font-data)',
          fontSize: 14,
          flexShrink: 0,
        }}
        className="cursor-blink"
      >
        █
      </span>
    </div>
  );
};
