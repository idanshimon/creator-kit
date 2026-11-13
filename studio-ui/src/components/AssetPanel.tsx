import { useRef, useState } from 'react';
import { Upload, Plus, Film } from 'lucide-react';
import type { Asset } from '../lib/api';
import { MAX_UPLOAD_BYTES } from '../lib/timeline';
import { Button } from './ui';

// Left panel: import videos (binary upload) + asset library -> add to timeline.

export function AssetPanel(props: {
  assets: Asset[];
  uploading: boolean;
  onUpload: (file: File) => void;
  onAdd: (asset: Asset) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);

  function pick(files: FileList | null) {
    setLocalErr(null);
    const file = files && files[0];
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalErr(`Too large: ${(file.size / 1048576).toFixed(0)} MiB (max 256 MiB)`);
      return;
    }
    props.onUpload(file);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span>Assets</span>
        <Button
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={props.uploading}
          title="Import video"
        >
          <Upload size={14} /> {props.uploading ? 'Uploading…' : 'Import'}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          style={{ display: 'none' }}
          onChange={(e) => pick(e.target.files)}
        />
      </div>
      <div className="panel-body">
        {localErr && <div className="alert">{localErr}</div>}
        {props.assets.length === 0 && <div className="muted">No assets. Import a video to begin.</div>}
        {props.assets.map((a) => (
          <div className="asset" key={a.id}>
            <Film size={16} className="muted" />
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="name truncate">{a.name}</div>
              <div className="meta mono">
                {a.width}×{a.height} · {a.duration.toFixed(1)}s · {a.has_audio ? 'audio' : 'silent'}
              </div>
            </div>
            <Button size="icon" className="sm" onClick={() => props.onAdd(a)} title="Add to timeline">
              <Plus size={14} />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
