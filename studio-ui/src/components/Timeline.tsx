import { ArrowUp, ArrowDown, Copy, Scissors, Trash2 } from 'lucide-react';
import type { Asset } from '../lib/api';
import type { Clip } from '../lib/timeline';
import { clipDuration } from '../lib/timeline';
import { Button, fmt } from './ui';

// Timeline: ordered clip list with select / reorder / duplicate / split / remove.

export function Timeline(props: {
  clips: Clip[];
  assets: Asset[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMove: (index: number, delta: number) => void;
  onDuplicate: (index: number) => void;
  onSplit: (index: number) => void;
  onRemove: (index: number) => void;
}) {
  const nameFor = (assetId: string) => props.assets.find((a) => a.id === assetId)?.name || '(missing asset)';

  return (
    <div className="timeline">
      <div className="section-title">Timeline · {props.clips.length} clip(s)</div>
      {props.clips.length === 0 && <div className="muted">Empty timeline. Add an asset from the left.</div>}
      {props.clips.map((c, i) => (
        <div
          key={c.id}
          className={['clip', c.id === props.selectedId ? 'selected' : ''].filter(Boolean).join(' ')}
          onClick={() => props.onSelect(c.id)}
        >
          <span className="idx mono">{i + 1}</span>
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="clip-name truncate">{nameFor(c.asset_id)}</div>
            <div className="clip-meta mono">
              In {fmt(c.in)} · Out {fmt(c.out)} · {fmt(clipDuration(c))} · {c.speed}× · vol {c.volume}
              {c.mute ? ' · muted' : ''}
            </div>
          </div>
          <div className="clip-actions" onClick={(e) => e.stopPropagation()}>
            <Button size="icon" className="sm" onClick={() => props.onMove(i, -1)} disabled={i === 0} title="Move up">
              <ArrowUp size={14} />
            </Button>
            <Button
              size="icon"
              className="sm"
              onClick={() => props.onMove(i, 1)}
              disabled={i === props.clips.length - 1}
              title="Move down"
            >
              <ArrowDown size={14} />
            </Button>
            <Button size="icon" className="sm" onClick={() => props.onDuplicate(i)} title="Duplicate">
              <Copy size={14} />
            </Button>
            <Button size="icon" className="sm" onClick={() => props.onSplit(i)} title="Split at source midpoint">
              <Scissors size={14} />
            </Button>
            <Button size="icon" className="sm danger" onClick={() => props.onRemove(i)} title="Remove">
              <Trash2 size={14} />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
