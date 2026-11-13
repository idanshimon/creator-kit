import type React from 'react';

// Small presentational primitives. components/ui is the design-system swap point:
// replace this file to reskin; domain components never hardcode colors.

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary' | 'danger' | 'ghost';
  size?: 'default' | 'sm' | 'icon';
};

export function Button({ variant = 'default', size = 'default', className = '', ...props }: BtnProps) {
  const cls = ['btn', variant !== 'default' ? variant : '', size !== 'default' ? size : '', className]
    .filter(Boolean)
    .join(' ');
  return <button className={cls} {...props} />;
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

export function Badge({
  kind,
  children,
}: {
  kind?: 'dirty' | 'stale' | 'ok';
  children: React.ReactNode;
}) {
  return (
    <span className={['badge', kind || ''].filter(Boolean).join(' ')}>
      <span className="dot" />
      {children}
    </span>
  );
}

// fmt: seconds -> mm:ss.d, always numeric (never injects markup)
export function fmt(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(1).padStart(4, '0')}`;
}
