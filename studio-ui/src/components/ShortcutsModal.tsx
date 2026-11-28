import { X, Keyboard } from 'lucide-react';
import { Button } from './ui';

const SHORTCUTS = [
  { keys: 'Space', desc: 'Play / pause source video' },
  { keys: 'I', desc: 'Set clip In point at playhead' },
  { keys: 'O', desc: 'Set clip Out point at playhead' },
  { keys: 'S', desc: 'Split selected clip at playhead' },
  { keys: 'Ctrl / ⌘ + S', desc: 'Save revision' },
  { keys: 'Ctrl / ⌘ + Z', desc: 'Undo' },
  { keys: 'Ctrl / ⌘ + Shift + Z', desc: 'Redo' },
  { keys: '?', desc: 'Toggle keyboard shortcuts' },
  { keys: 'Esc', desc: 'Close modal' },
];

export function ShortcutsModal(props: { open: boolean; onClose: () => void }) {
  if (!props.open) return null;
  return (
    <div className="modal-backdrop" onClick={props.onClose} role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="row" style={{ gap: 6, fontWeight: 600 }}>
            <Keyboard size={15} /> Keyboard Shortcuts
          </span>
          <Button size="icon" className="ghost sm" onClick={props.onClose} aria-label="Close shortcuts">
            <X size={15} />
          </Button>
        </div>
        <div className="modal-body">
          {SHORTCUTS.map((s) => (
            <div className="shortcut-row" key={s.keys}>
              <span className="shortcut-desc">{s.desc}</span>
              <kbd className="kbd mono">{s.keys}</kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
