import type { Plan, PresetName } from '../lib/timeline';
import { PRESETS, VOLUME_MIN, VOLUME_MAX } from '../lib/timeline';
import { Field } from './ui';

// Output/composition settings: preset, contain/cover, global volume, fades.

const PRESET_LABEL: Record<PresetName, string> = {
  landscape: 'Landscape 1280×720',
  portrait: 'Portrait 720×1280',
  square: 'Square 1080×1080',
};

export function OutputSettings(props: { plan: Plan; onPatch: (patch: Partial<Plan>) => void }) {
  const { plan } = props;
  const preset = plan.preset || 'landscape';
  const fit = plan.fit || 'contain';
  const vol = plan.volume ?? 1;
  return (
    <div className="panel-body" style={{ padding: 0, gap: 10 }}>
      <div className="section-title">Output</div>

      <Field label="Preset">
        <select
          className="select"
          value={preset}
          onChange={(e) => props.onPatch({ preset: e.target.value as PresetName })}
        >
          {(Object.keys(PRESETS) as PresetName[]).map((p) => (
            <option key={p} value={p}>
              {PRESET_LABEL[p]}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Fit">
        <select className="select" value={fit} onChange={(e) => props.onPatch({ fit: e.target.value as 'contain' | 'cover' })}>
          <option value="contain">Contain (letterbox)</option>
          <option value="cover">Cover (crop to fill)</option>
        </select>
      </Field>

      <Field label={`Global volume — ${vol.toFixed(2)}`}>
        <input
          className="range"
          type="range"
          min={VOLUME_MIN}
          max={VOLUME_MAX}
          step={0.05}
          value={vol}
          onChange={(e) => props.onPatch({ volume: parseFloat(e.target.value) })}
        />
      </Field>

      <div className="row">
        <Field label="Fade in (s)">
          <input
            className="input"
            type="number"
            min={0}
            step={0.1}
            value={plan.fade_in ?? 0}
            onChange={(e) => props.onPatch({ fade_in: Math.max(0, parseFloat(e.target.value) || 0) })}
          />
        </Field>
        <Field label="Fade out (s)">
          <input
            className="input"
            type="number"
            min={0}
            step={0.1}
            value={plan.fade_out ?? 0}
            onChange={(e) => props.onPatch({ fade_out: Math.max(0, parseFloat(e.target.value) || 0) })}
          />
        </Field>
      </div>
    </div>
  );
}
