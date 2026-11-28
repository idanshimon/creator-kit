import { useRef, useState } from 'react';
import { Upload, Plus, Film, Search, X } from 'lucide-react';
import type { Asset } from '../lib/api';
import { MAX_UPLOAD_BYTES } from '../lib/timeline';
import { Button } from './ui';

// Left panel: import videos (binary upload + drag-and-drop) + filterable asset library -> add to timeline.

export function AssetPanel(props: {
  assets: Asset[];
  uploading: boolean;
  onUpload: (file: File) => void;
  onAdd: (asset: Asset) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [query, setQuery] = useState('');

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

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!dragging) setDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    if (props.uploading) return;
    pick(e.dataTransfer.files);
  }

  const trimmed = query.trim().toLowerCase();
  const filtered = trimmed
    ? props.assets.filter((a) => a.name.toLowerCase().includes(trimmed))
    : props.assets;

  return (
    <div className="panel">
      <div className="panel-head">
        <span>Assets{props.assets.length > 0 ? ` (${props.assets.length})` : ''}</span>
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

        <div
          className={['dropzone', dragging ? 'active' : ''].filter(Boolean).join(' ')}
          onDragEnter={handleDragOver}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !props.uploading && inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              if (!props.uploading) inputRef.current?.click();
            }
          }}
        >
          <Upload size={15} />
          <span>{dragging ? 'Drop video to import' : 'Drop video here or click to import'}</span>
        </div>

        {props.assets.length > 0 && (
          <div className="search-wrap">
            <Search size={13} className="search-icon" />
            <input
              className="input search-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter assets…"
              aria-label="Filter assets"
            />
            {query && (
              <button
                type="button"
                className="search-clear"
                onClick={() => setQuery('')}
                aria-label="Clear filter"
                title="Clear filter"
              >
                <X size={13} />
              </button>
            )}
          </div>
        )}

        {props.assets.length === 0 && <div className="muted">No assets. Import a video to begin.</div>}
        {props.assets.length > 0 && filtered.length === 0 && (
          <div className="muted">No matching assets.</div>
        )}
        {filtered.map((a) => (
          <div className="asset" key={a.id}>
            <Film size={16} className="muted" style={{ flexShrink: 0 }} />
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
