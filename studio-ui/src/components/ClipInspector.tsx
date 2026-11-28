import { VolumeX, Volume2, RotateCcw } from 'lucide-react';
import type { Clip } from '../lib/timeline';
import { SPEED_MIN, SPEED_MAX, VOLUME_MIN, VOLUME_MAX, clipDuration } from '../lib/timeline';
import { Button, Field, fmt } from './ui';

// Per-clip inspector: trim + effective duration readout, speed presets & slider,
// volume presets & slider, mute toggle, reset clip.

const SPEED_PRESETS = [0.5, 1, 1.25, 1.5, 2];
const VOLUME_PRESETS = [
  { label: '50%', value: 0.5 },
  { label: '100%', value: 1 },
  { label: '150%', value: 1.5 },
];

export function ClipInspector(props: {
  clip: Clip | null;
  onPatch: (patch: Partial<Clip>) => void;
  onResetClip: () => void;
}) {
  const { clip } = props;
  if (!clip) return <div className="muted">No clip selected.</div>;

  const effDur = clipDuration(clip);
  const isDefault = clip.speed === 1 && clip.volume === 1 && !clip.mute;

  return (
    <div className="panel-body" style={{ padding: 0, gap: 10 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="section-title">Clip</div>
        <Button
          size="sm"
          variant="ghost"
          onClick={props.onResetClip}
          disabled={isDefault}
          title="Reset speed, volume, and mute"
        >
          <RotateCcw size={12} /> Reset Clip
        </Button>
      </div>

      <div className="readout-box mono">
        <div className="muted">
          In {fmt(clip.in)} · Out {fmt(clip.out)}
        </div>
        <div className="readout-highlight">
          Effective: <strong>{fmt(effDur)}</strong>
        </div>
      </div>

      <Field label={`Speed — ${clip.speed}×`}>
        <input
          className="range"
          type="range"
          min={SPEED_MIN}
          max={SPEED_MAX}
          step={0.05}
          value={clip.speed}
          onChange={(e) => props.onPatch({ speed: parseFloat(e.target.value) })}
        />
        <div className="preset-row">
          {SPEED_PRESETS.map((s) => (
            <button
              key={s}
              type="button"
              className={['pill-btn', Math.abs(clip.speed - s) < 0.01 ? 'active' : ''].filter(Boolean).join(' ')}
              onClick={() => props.onPatch({ speed: s })}
            >
              {s}×
            </button>
          ))}
        </div>
      </Field>

      <Field label={`Volume — ${Math.round(clip.volume * 100)}% (${clip.volume.toFixed(2)})`}>
        <input
          className="range"
          type="range"
          min={VOLUME_MIN}
          max={VOLUME_MAX}
          step={0.05}
          value={clip.volume}
          onChange={(e) => props.onPatch({ volume: parseFloat(e.target.value) })}
        />
        <div className="preset-row">
          {VOLUME_PRESETS.map((v) => (
            <button
              key={v.value}
              type="button"
              className={['pill-btn', Math.abs(clip.volume - v.value) < 0.01 ? 'active' : ''].filter(Boolean).join(' ')}
              onClick={() => props.onPatch({ volume: v.value })}
            >
              {v.label}
            </button>
          ))}
        </div>
      </Field>

      <Button
        size="sm"
        variant={clip.mute ? 'danger' : 'default'}
        onClick={() => props.onPatch({ mute: !clip.mute })}
      >
        {clip.mute ? <VolumeX size={14} /> : <Volume2 size={14} />}
        {clip.mute ? 'Muted' : 'Mute clip'}
      </Button>
    </div>
  );
}
