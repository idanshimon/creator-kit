import { VolumeX, Volume2 } from 'lucide-react';
import type { Clip } from '../lib/timeline';
import { SPEED_MIN, SPEED_MAX, VOLUME_MIN, VOLUME_MAX } from '../lib/timeline';
import { Button, Field, fmt } from './ui';

// Per-clip inspector: trim readout, speed 0.25..4, volume 0..2, mute.

export function ClipInspector(props: {
  clip: Clip | null;
  onPatch: (patch: Partial<Clip>) => void;
}) {
  const { clip } = props;
  if (!clip) return <div className="muted">No clip selected.</div>;
  return (
    <div className="panel-body" style={{ padding: 0, gap: 10 }}>
      <div className="section-title">Clip</div>
      <div className="mono muted">
        In {fmt(clip.in)} · Out {fmt(clip.out)}
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
      </Field>

      <Field label={`Volume — ${clip.volume.toFixed(2)}`}>
        <input
          className="range"
          type="range"
          min={VOLUME_MIN}
          max={VOLUME_MAX}
          step={0.05}
          value={clip.volume}
          onChange={(e) => props.onPatch({ volume: parseFloat(e.target.value) })}
        />
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
