import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Play, Pause, LogIn, LogOut, RotateCcw, Scissors, SkipBack, SkipForward } from 'lucide-react';
import type { Asset } from '../lib/api';
import type { Clip } from '../lib/timeline';
import { Button, fmt } from './ui';

// Source preview: shows the SELECTED CLIP'S SOURCE video (not the composited timeline),
// with transport controls, seek + visual In→Out trim highlight bar, and trim actions.

export interface SourcePreviewHandle {
  togglePlay: () => void;
  setInAtPlayhead: () => void;
  setOutAtPlayhead: () => void;
  splitAtPlayhead: () => void;
}

export const SourcePreview = forwardRef<
  SourcePreviewHandle,
  {
    clip: Clip | null;
    asset: Asset | null;
    onSetIn: (t: number) => void;
    onSetOut: (t: number) => void;
    onResetTrim: () => void;
    onSplitAtPlayhead: (t: number) => void;
  }
>(function SourcePreview(props, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [dur, setDur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const { clip, asset } = props;

  // Reload the media when the underlying asset changes.
  useEffect(() => {
    const v = videoRef.current;
    if (v && asset) {
      v.load();
      setTime(0);
      setPlaying(false);
    }
  }, [asset?.id]);

  const maxDur = Math.max(dur, asset?.duration || 0);

  function seek(t: number) {
    const clamped = Math.min(Math.max(0, t), maxDur || 0);
    const v = videoRef.current;
    if (v) {
      v.currentTime = clamped;
      setTime(clamped);
    }
  }

  function togglePlay() {
    const v = videoRef.current;
    if (!v || !clip || !asset) return;
    if (v.paused) {
      v.play().catch(() => {});
    } else {
      v.pause();
    }
  }

  useImperativeHandle(ref, () => ({
    togglePlay,
    setInAtPlayhead: () => {
      if (clip && asset) props.onSetIn(videoRef.current?.currentTime ?? time);
    },
    setOutAtPlayhead: () => {
      if (clip && asset) props.onSetOut(videoRef.current?.currentTime ?? time);
    },
    splitAtPlayhead: () => {
      if (clip && asset) props.onSplitAtPlayhead(videoRef.current?.currentTime ?? time);
    },
  }));

  if (!clip || !asset) {
    return (
      <div className="preview-wrap">
        <span className="preview-label">Source</span>
        <span className="preview-empty">Select a clip to preview its source.</span>
      </div>
    );
  }

  const inPct = maxDur > 0 ? Math.min(100, Math.max(0, (clip.in / maxDur) * 100)) : 0;
  const outPct = maxDur > 0 ? Math.min(100, Math.max(inPct, (clip.out / maxDur) * 100)) : 100;
  const playPct = maxDur > 0 ? Math.min(100, Math.max(0, (time / maxDur) * 100)) : 0;
  const isTrimmed = clip.in > 0.01 || Math.abs(clip.out - asset.duration) > 0.05;

  return (
    <>
      <div className="preview-wrap">
        <span className="preview-label">Source · {asset.name}</span>
        <video
          ref={videoRef}
          src={asset.url}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          controls
          preload="metadata"
        />
      </div>

      <div className="transport">
        <Button
          size="sm"
          onClick={togglePlay}
          title={playing ? 'Pause (Space)' : 'Play (Space)'}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}
          {playing ? 'Pause' : 'Play'}
        </Button>
        <Button size="sm" onClick={() => seek(time - 1)} title="Step back 1 second">
          -1s
        </Button>
        <Button size="sm" onClick={() => seek(time + 1)} title="Step forward 1 second">
          +1s
        </Button>

        <span className="mono muted transport-time">{fmt(time)}</span>
        <div className="seek-wrap">
          <input
            className="seek"
            type="range"
            min={0}
            max={maxDur || 0}
            step={0.1}
            value={time}
            onChange={(e) => seek(parseFloat(e.target.value))}
            aria-label="Seek source"
          />
          <div className="trim-track" aria-hidden="true">
            <div
              className="trim-range"
              style={{ left: `${inPct}%`, width: `${Math.max(0, outPct - inPct)}%` }}
            />
            <div className="trim-playhead" style={{ left: `${playPct}%` }} />
          </div>
        </div>
        <span className="mono muted transport-time right">{fmt(maxDur)}</span>
      </div>

      <div className="transport transport-actions" style={{ borderTop: 0 }}>
        <Button size="sm" onClick={() => props.onSetIn(time)} title="Set in at playhead (I)">
          <LogIn size={14} /> Set In
        </Button>
        <Button size="sm" onClick={() => props.onSetOut(time)} title="Set out at playhead (O)">
          <LogOut size={14} /> Set Out
        </Button>
        <Button size="sm" onClick={() => seek(clip.in)} title="Jump playhead to In point">
          <SkipBack size={13} /> In
        </Button>
        <Button size="sm" onClick={() => seek(clip.out)} title="Jump playhead to Out point">
          <SkipForward size={13} /> Out
        </Button>
        <Button size="sm" onClick={() => props.onSplitAtPlayhead(time)} title="Split at playhead source time (S)">
          <Scissors size={13} /> Split @ Playhead
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={props.onResetTrim}
          disabled={!isTrimmed}
          title="Reset trim to full asset duration"
        >
          <RotateCcw size={13} /> Reset Trim
        </Button>
        <span className="mono muted grow transport-readout">
          In {fmt(clip.in)} · Out {fmt(clip.out)}
        </span>
      </div>
    </>
  );
});
