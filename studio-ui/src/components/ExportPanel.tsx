import { Download, Film, Loader2 } from 'lucide-react';
import type { Job, Project } from '../lib/api';
import { Button, Badge } from './ui';

// Export panel: draft/final render, live job list from real /api/state polling,
// rendered-video preview + download, revision + stale marking.

export function ExportPanel(props: {
  project: Project;
  jobs: Job[];
  dirty: boolean;
  busy: boolean;
  onRender: (kind: 'draft' | 'final') => void;
}) {
  // Jobs for this project, newest first.
  const jobs = props.jobs
    .filter((j) => j.project_id === props.project.id)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  return (
    <div className="panel-body" style={{ padding: 0, gap: 10 }}>
      <div className="section-title">Export</div>
      {props.dirty && <div className="alert warn">Unsaved changes — save before exporting to render the latest.</div>}
      <div className="row">
        <Button
          className="grow"
          onClick={() => props.onRender('draft')}
          disabled={props.busy || props.dirty}
          title="Fast draft render"
        >
          <Film size={14} /> Draft
        </Button>
        <Button
          variant="primary"
          className="grow"
          onClick={() => props.onRender('final')}
          disabled={props.busy || props.dirty}
          title="Full-quality render"
        >
          <Film size={14} /> Final
        </Button>
      </div>

      {jobs.length === 0 && <div className="muted">No renders yet.</div>}

      {jobs.map((j) => {
        const stale = j.revision < props.project.revision;
        const running = j.status === 'queued' || j.status === 'running';
        return (
          <div className="job" key={j.id}>
            <div className="job-head">
              <span className="mono">
                {j.kind} · r{j.revision}
              </span>
              {j.status === 'succeeded' ? (
                <Badge kind={stale ? 'stale' : 'ok'}>{stale ? 'stale' : 'done'}</Badge>
              ) : j.status === 'failed' ? (
                <Badge kind="stale">error</Badge>
              ) : (
                <span className="badge">
                  <Loader2 size={11} /> {j.status}
                </span>
              )}
            </div>

            {j.error && <div className="alert">{j.error}</div>}

            {j.status === 'succeeded' && j.result_url && (
              <>
                {stale && <div className="alert warn">Rendered from r{j.revision}; project is now r{props.project.revision}.</div>}
                <video src={j.result_url} controls preload="metadata" style={{ width: '100%', background: '#000' }} />
                <a href={j.result_url} download>
                  <Button size="sm" className="grow" title="Download rendered video">
                    <Download size={14} /> Download
                  </Button>
                </a>
              </>
            )}
            {running && <div className="muted mono">rendering…</div>}
          </div>
        );
      })}
    </div>
  );
}
