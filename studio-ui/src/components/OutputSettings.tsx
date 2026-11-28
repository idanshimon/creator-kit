import type { Plan, PresetName } from '../lib/timeline';
import { PRESETS, VOLUME_MIN, VOLUME_MAX } from '../lib/timeline';
import { Field } from './ui';

// Output/composition settings: preset pills + selector, contain/cover, global volume, fades + quick fade presets.

const PRESET_LABEL: Record<PresetName, string> = {
  landscape: 'Landscape 1280×720',
  portrait: 'Portrait 720×1280',
  square: 'Square 1080×1080',
};

const PRESET_PILLS: Array<{ key: PresetName; ratio: string }> = [
  { key: 'landscape', ratio: '16:9' },
  { key: 'portrait', ratio: '9:16' },
  { key: 'square', ratio: '1:1' },
];

const FADE_PRESETS = [0, 0.3, 0.5, 1];

export function OutputSettings(props: { plan: Plan; onPatch: (patch: Partial<Plan>) => void }) {
  const { plan } = props;
  const preset = plan.preset || 'landscape';
  const fit = plan.fit || 'contain';
  const vol = plan.volume ?? 1;
  const fadeIn = plan.fade_in ?? 0;
  const fadeOut = plan.fade_out ?? 0;

  return (
    <div className="panel-body" style={{ padding: 0, gap: 10 }}>
      <div className="section-title">Output</div>

      <Field label="Preset">
        <div className="preset-row" style={{ marginBottom: 4 }}>
          {PRESET_PILLS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={['pill-btn', preset === p.key ? 'active' : ''].filter(Boolean).join(' ')}
              onClick={() => props.onPatch({ preset: p.key })}
              title={PRESET_LABEL[p.key]}
            >
              {p.ratio}
            </button>
          ))}
        </div>
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
        <div className="grow">
          <Field label="Fade in (s)">
            <input
              className="input"
              type="number"
              min={0}
              step={0.1}
              value={fadeIn}
              onChange={(e) => props.onPatch({ fade_in: Math.max(0, parseFloat(e.target.value) || 0) })}
            />
            <div className="preset-row preset-grid-4">
              {FADE_PRESETS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={['pill-btn', Math.abs(fadeIn - s) < 0.01 ? 'active' : ''].filter(Boolean).join(' ')}
                  onClick={() => props.onPatch({ fade_in: s })}
                  title={`Set fade in to ${s}s`}
                >
                  {s}s
                </button>
              ))}
            </div>
          </Field>
        </div>
        <div className="grow">
          <Field label="Fade out (s)">
            <input
              className="input"
              type="number"
              min={0}
              step={0.1}
              value={fadeOut}
              onChange={(e) => props.onPatch({ fade_out: Math.max(0, parseFloat(e.target.value) || 0) })}
            />
            <div className="preset-row preset-grid-4">
              {FADE_PRESETS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={['pill-btn', Math.abs(fadeOut - s) < 0.01 ? 'active' : ''].filter(Boolean).join(' ')}
                  onClick={() => props.onPatch({ fade_out: s })}
                  title={`Set fade out to ${s}s`}
                >
                  {s}s
                </button>
              ))}
            </div>
          </Field>
        </div>
      </div>
    </div>
  );
}
