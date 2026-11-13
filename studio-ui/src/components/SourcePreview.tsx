import { useEffect, useRef, useState } from 'react';
import { LogIn, LogOut } from 'lucide-react';
import type { Asset } from '../lib/api';
import type { Clip } from '../lib/timeline';
import { Button, fmt } from './ui';

// Source preview: shows the SELECTED CLIP'S SOURCE video (not the composited timeline),
// with seek + trim (Set In / Set Out at playhead). Explicitly labeled "SOURCE".

export function SourcePreview(props: {
  clip: Clip | null;
  asset: Asset | null;
  onSetIn: (t: number) => void;
  onSetOut: (t: number) => void;
  onSplitAtPlayhead: (t: number) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [dur, setDur] = useState(0);
  const { clip, asset } = props;

  // Reload the media when the underlying asset changes.
  useEffect(() => {
    const v = videoRef.current;
    if (v && asset) {
      v.load();
      setTime(0);
    }
  }, [asset?.id]);

  if (!clip || !asset) {
    return (
      <div className="preview-wrap">
        <span className="preview-label">Source</span>
        <span className="preview-empty">Select a clip to preview its source.</span>
      </div>
    );
  }

  function seek(t: number) {
    const v = videoRef.current;
    if (v) {
      v.currentTime = t;
      setTime(t);
    }
  }

  return (
    <>
      <div className="preview-wrap">
        <span className="preview-label">Source · {asset.name}</span>
        <video
          ref={videoRef}
          src={asset.url}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
          controls
          preload="metadata"
        />
      </div>

      <div className="transport">
        <span className="mono muted" style={{ width: 64 }}>
          {fmt(time)}
        </span>
        <input
          className="seek"
          type="range"
          min={0}
          max={Math.max(dur, asset.duration) || 0}
          step={0.1}
          value={time}
          onChange={(e) => seek(parseFloat(e.target.value))}
          aria-label="Seek source"
        />
        <span className="mono muted" style={{ width: 64, textAlign: 'right' }}>
          {fmt(dur || asset.duration)}
        </span>
      </div>

      <div className="transport" style={{ borderTop: 0 }}>
        <Button size="sm" onClick={() => props.onSetIn(time)} title="Set in at playhead">
          <LogIn size={14} /> Set In
        </Button>
        <Button size="sm" onClick={() => props.onSetOut(time)} title="Set out at playhead">
          <LogOut size={14} /> Set Out
        </Button>
        <Button size="sm" onClick={() => props.onSplitAtPlayhead(time)} title="Split at playhead source time">
          Split @ Playhead
        </Button>
        <span className="mono muted grow" style={{ textAlign: 'right' }}>
          In {fmt(clip.in)} · Out {fmt(clip.out)}
        </span>
      </div>
    </>
  );
}
